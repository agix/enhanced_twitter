import twitter
import requests
import redis
import sys
from bottle import route, run, template, response
from json import dumps, loads
import secret
import datetime
from progress.bar import Bar
import numpy as np

if len(sys.argv) != 2:
    print 'Usage: python %s <pull|qualify|train|test> (tweet id)'%sys.argv[0]
    sys.exit(0)

r = redis.StrictRedis(host='localhost', port=6379, db=3)

def addFeature(statusDict, key, func=lambda x: x, default = 0):
    if key in statusDict:
        feature = func(statusDict[key])
    else:
        feature = default

    return feature

def getTweetInfos(statusDict, nbTweets = -1):
    filteredDict = {}
    filteredDict['favorite_count']   = addFeature(statusDict, 'favorite_count')
    filteredDict['retweet_count']    = addFeature(statusDict, 'retweet_count')
    filteredDict['created_at']       = addFeature(statusDict, 'created_at')
    
    filteredDict['nbMedia']          = addFeature(statusDict, 'media', len)
    filteredDict['nbUser_mentions']  = addFeature(statusDict, 'user_mentions', len)
    filteredDict['user_mentions']    = addFeature(statusDict, 'user_mentions', lambda x: ' '.join(' '.join([y['screen_name'] for y in x])))
    filteredDict['nbHashtags']       = addFeature(statusDict, 'hashtags', len)
    filteredDict['hashtags']         = addFeature(statusDict, 'hashtags', lambda x: ' '.join(x), '')
    
    filteredDict['text']             = statusDict['text']


    filteredDict.update(getUserInfos(statusDict, 'user', nbTweets))

    return filteredDict


def getUserInfos(statusDict, prefix = 'origuser', nbTweets = -1):
    filteredDict = {}
    filteredDict[prefix+'Followers_count']  = addFeature(statusDict, 'followers_count')
    filteredDict[prefix+'Friends_count']    = addFeature(statusDict, 'friends_count')
    filteredDict[prefix+'Protected']        = statusDict['user']['protected']
    filteredDict[prefix+'Lang']             = statusDict['user']['lang']
    filteredDict[prefix+'Id']               = statusDict['user']['id']
    filteredDict[prefix+'Screen_name']      = statusDict['user']['screen_name']
    filteredDict[prefix+'Verified']         = 'verified' in statusDict['user']
    if nbTweets == -1:
        filteredDict[prefix+'NbTweetsHour'] = getNbTweets(statusDict['user']['id'], statusDict['id'], statusDict['created_at'])
    else:
        filteredDict[prefix+'NbTweetsHour'] = nbTweets
    return filteredDict

def getNbTweets(userId, max_id, created_at, minutes = 60, count = 20):
    global api
    fromDate = datetime.datetime.strptime(created_at, '%a %b %d %H:%M:%S +0000 %Y')
    toDate = fromDate - datetime.timedelta(minutes = minutes)
    statuses = api.GetUserTimeline(userId, max_id=max_id, count=count, exclude_replies=True)
    nb = 0
    for status in statuses:
        statusDict = status.AsDict()
        date = datetime.datetime.strptime(statusDict['created_at'], '%a %b %d %H:%M:%S +0000 %Y')
        if date > toDate:
            nb += 1
    return nb



if sys.argv[1] == 'pull':
    count = 150
    api = twitter.Api(
        consumer_key        = secret.consumer_key, 
        consumer_secret     = secret.consumer_secret, 
        access_token_key    = secret.access_token_key, 
        access_token_secret = secret.access_token_secret
    )

    statuses = api.GetHomeTimeline(count=count)
    print "Got your timeline"
    bar = Bar('Processing', max=count)
    for status in statuses:
        statusDict = status.AsDict()
        bar.next()

        try:
            filteredDict = {
                'retweeted' : statusDict['retweeted'],
                'favorited' : statusDict['favorited'],
                'lang'      : statusDict['lang'],
            }
            origuser = getUserInfos(statusDict)
            filteredDict.update(origuser)
                
            if 'retweeted_status' in statusDict:
                filteredDict['retweeted_status'] = 1
                filteredDict.update(getTweetInfos(statusDict['retweeted_status']))
                created_at = datetime.datetime.strptime(statusDict['retweeted_status']['created_at'], '%a %b %d %H:%M:%S +0000 %Y')
            else:
                filteredDict['retweeted_status'] = 0
                filteredDict.update(getTweetInfos(statusDict, origuser['origuserNbTweetsHour']))
                created_at = datetime.datetime.strptime(statusDict['created_at'], '%a %b %d %H:%M:%S +0000 %Y')

        except Exception as e:
            bar.finish()
            try:
                if e[0][0]['code'] == 88:
                    print e[0][0]['message']
                    sys.exit()
            except Exception as e2:
                print e2
                print status.AsJsonString()

        tweetId = '%04d%02d%02d_%d'%(created_at.year, created_at.month, created_at.day, statusDict['id'])
        r.hmset(tweetId, filteredDict)
    bar.finish()

elif sys.argv[1] == 'qualify':
    @route('/')
    def index():
        tweets = r.keys('*')
        return template('index', tweets=tweets)

    @route('/<id>')
    def tweet(id):
        like = r.hget(id, 'like')
        t = requests.get('https://api.twitter.com/1/statuses/oembed.json?url=https://twitter.com/Interior/status/'+id)
        content = loads(t.text)
        content['like'] = like
        response.content_type = 'application/json'
        return dumps(content);

    @route('/<id>/<state>')
    def choice(id, state):
        r.hset(id, 'like', state)
        response.content_type = 'application/json'
        return dumps('ok');

    run(host='localhost', port=8081)

elif sys.argv[1] == 'train':
    userLangs = {
        'en': float(1),
        'fr': float(2),
        'ht': float(3)
    }
    now = datetime.datetime.now()
    trainIds = r.keys('%04d%02d*'%(now.year, now.month))
    trainSamples = []
    targetSamples = []
    for trainId in trainIds:
        trainRaw = r.hgetall(trainId)
        trainSample = [
            userLangs[trainRaw['userLang']], float(trainRaw['retweeted_status']), float(bool(trainRaw['userProtected'])), 
            float(bool(trainRaw['origuserVerified'])), userLangs[trainRaw['origuserLang']], float(bool(trainRaw['origuserProtected'])),
            userLangs[trainRaw['lang']], float(trainRaw['userFollowers_count']), float(trainRaw['favorite_count']),
            float(trainRaw['userId']), float(trainRaw['origuserId']), float(bool(trainRaw['userVerified'])), float(trainRaw['userNbTweetsHour']),
            float(trainRaw['nbUser_mentions']), float(trainRaw['origuserFriends_count']), float(trainRaw['origuserFollowers_count']),
            float(bool(trainRaw['retweeted'])), float(trainRaw['origuserNbTweetsHour']), float(trainRaw['nbMedia']), float(trainRaw['userFriends_count']),
            float(trainRaw['retweet_count']), float(bool(trainRaw['favorited'])), float(trainRaw['nbHashtags'])
        ]
        if 'like' in trainRaw:
            targetSamples.append(float(trainRaw['like']))
        else:
            targetSamples.append(float(0))

        trainSamples.append(trainSample)

    targetSamples = np.array(targetSamples)
    trainSamples  = np.array(trainSamples)
    print trainSamples


# "userLang"
# "retweeted_status"
# "userProtected"
# "origuserVerified"
# "origuserLang"
# "origuserProtected"
# "hashtags"
# "lang"
# "userFollowers_count"
# "favorite_count"
# "userId"
# "origuserId"
# "userVerified"
# "userNbTweetsHour"
# "nbUser_mentions"
# "origuserScreen_name"
# "created_at"
# "origuserFriends_count"
# "origuserFollowers_count"
# "userScreen_name"
# "retweeted"
# "origuserNbTweetsHour"
# "nbMedia"
# "userFriends_count"
# "retweet_count"
# "favorited"
# "user_mentions"
# "text"
# "nbHashtags"
