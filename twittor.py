import twitter
import requests
import redis
import sys
from bottle import route, run, template, response
from json import dumps, loads
import secret

if len(sys.argv) != 2:
    print 'Usage: python %s <pull|qualify|train>'%sys.argv[0]
    sys.exit(0)

r = redis.StrictRedis(host='localhost', port=6379, db=3)

def addFeature(statusDict, key, func=lambda x: x, default = 0):
    if key in statusDict:
        feature = func(statusDict[key])
    else:
        feature = default

    return feature

def getTweetInfos(statusDict):
    filteredDict = {}
    filteredDict['favorite_count'] = addFeature(statusDict, 'favorite_count')
    filteredDict['retweet_count']  = addFeature(statusDict, 'retweet_count')
    filteredDict['created_at']     = addFeature(statusDict, 'created_at')
    
    filteredDict['media']          = addFeature(statusDict, 'media', len)
    filteredDict['hashtags']       = addFeature(statusDict, 'hashtags', lambda x: ' '.join(x), '')
    
    filteredDict['text']           = statusDict['text']

    filteredDict.update(getUserInfos(statusDict))

    return filteredDict


def getUserInfos(statusDict, prefix = 'user'):
    filteredDict = {}
    filteredDict[prefix+'Followers_count'] = addFeature(statusDict, 'followers_count')
    filteredDict[prefix+'Friends_count']   = addFeature(statusDict, 'friends_count')
    filteredDict[prefix+'Protected']       = statusDict['user']['protected']
    filteredDict[prefix+'Lang']            = statusDict['user']['lang']
    filteredDict[prefix+'Id']              = statusDict['user']['id']
    filteredDict[prefix+'Verified']        = 'verified' in statusDict['user']
    return filteredDict


if sys.argv[1] == 'pull':
    api = twitter.Api(
        consumer_key        = secret.consumer_key, 
        consumer_secret     = secret.consumer_secret, 
        access_token_key    = secret.access_token_key, 
        access_token_secret = secret.access_token_secret
    )

    statuses = api.GetHomeTimeline(count=200)

    for status in statuses:
        statusDict = status.AsDict()
        try:
            filteredDict = {
                'retweeted' : statusDict['retweeted'],
                'favorited' : statusDict['favorited'],
                'lang'      : statusDict['lang'],
            }

            filteredDict.update(getUserInfos(statusDict, 'origuser'))
                
            if 'retweeted_status' in statusDict:
                filteredDict['retweeted_status'] = 1
                filteredDict.update(getTweetInfos(statusDict['retweeted_status']))
            else:
                filteredDict['retweeted_status'] = 0
                filteredDict.update(getTweetInfos(statusDict))
                
        except Exception as e:
            print e
            print status.AsJsonString()

            
        r.hmset(statusDict['id'], filteredDict)

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

    # tweet_ids = r.keys('*')
    # for tweet_id in tweet_ids:
    #     r.hget

#Status:
#favorite_count
#retweeted
#favorited
#retweet_count
#lang
#retweeted_status

#User:
#protected
#lang
#followers_count
#friends_count
#id
#verified

#OrigUser:
#protected
#lang
#followers_count
#friends_count
#id
#verified