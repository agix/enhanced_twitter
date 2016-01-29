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
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.model_selection import cross_val_predict
from sklearn import svm
from sklearn.metrics import accuracy_score
from sklearn.naive_bayes import GaussianNB
from sklearn.neural_network import MLPClassifier
import pickle
from textblob import TextBlob

if len(sys.argv) < 2:
    print 'Usage: python %s <pull|qualify|train|test>'%sys.argv[0]
    sys.exit(0)

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

def getFilteredDict(statusDict):
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
    else:
        filteredDict['retweeted_status'] = 0
        filteredDict.update(getTweetInfos(statusDict, origuser['origuserNbTweetsHour']))

    return filteredDict

def convertToScikit(trainRaw):
    langs = {
        'en' : float(1),
        'fr' : float(2),
        'ht' : float(3),
        'de' : float(4),
        'et' : float(5),
        'es' : float(6),
        'tl' : float(7),
        'in' : float(8),
        'da' : float(9),
        'und': float(10),
        'ro' : float(11),
        'it' : float(12),
        'zh-cn': float(13),
        'nl': float(14),
        'ru': float(15),
        'lt': float(16),
        'ja': float(17)
    }
    if trainRaw['lang'] != 'en':
        try:
            if type(trainRaw['text']) == type('ab'):
                blob = TextBlob(trainRaw['text'].decode('utf8'))
            else:
                blob = TextBlob(trainRaw['text'])
        except Exception as e:
            print type(trainRaw['text'])
            print trainRaw['text']
            blob = TextBlob(trainRaw['text'].decode('utf8'))
            sys.exit()
        try:
            text = blob.translate(to='en')
        except:
            text = blob
    else:
        try:
            if type(trainRaw['text']) == type('ab'):
                text = TextBlob(trainRaw['text'].decode('utf8'))
            else:
                text = TextBlob(trainRaw['text'])
        except Exception as e:
            print type(trainRaw['text'])
            print trainRaw['text']
            text = TextBlob(trainRaw['text'].decode('utf8'))
            sys.exit()
    polarity = text.sentiment.polarity
    subjectivity = text.sentiment.subjectivity

    trainSample = [
        langs[trainRaw['userLang']], float(trainRaw['retweeted_status']), float(bool(trainRaw['userProtected'])), 
        float(bool(trainRaw['origuserVerified'])), langs[trainRaw['origuserLang']], float(bool(trainRaw['origuserProtected'])),
        langs[trainRaw['lang']], float(trainRaw['userFollowers_count']), float(trainRaw['favorite_count']),
        float(trainRaw['userId']), float(trainRaw['origuserId']), float(bool(trainRaw['userVerified'])), float(trainRaw['userNbTweetsHour']),
        float(trainRaw['nbUser_mentions']), float(trainRaw['origuserFriends_count']), float(trainRaw['origuserFollowers_count']),
        float(bool(trainRaw['retweeted'])), float(trainRaw['origuserNbTweetsHour']), float(trainRaw['nbMedia']), float(trainRaw['userFriends_count']),
        float(trainRaw['retweet_count']), float(bool(trainRaw['favorited'])), float(trainRaw['nbHashtags']), polarity, subjectivity
    ]
    # trainSample = [
    #     langs[trainRaw['lang']], float(trainRaw['userFollowers_count']), float(trainRaw['favorite_count']),
    #     float(trainRaw['userId']), float(trainRaw['origuserId']), float(trainRaw['userNbTweetsHour']),
    #     float(trainRaw['nbUser_mentions']), float(trainRaw['origuserFriends_count']), float(trainRaw['origuserFollowers_count']),
    #     float(trainRaw['origuserNbTweetsHour']), float(trainRaw['nbMedia']), float(trainRaw['userFriends_count']),
    #     float(trainRaw['retweet_count']), float(trainRaw['nbHashtags']), polarity, subjectivity
    # ]
    

    return trainSample


r = redis.StrictRedis(host='localhost', port=6379, db=3)
r2 = redis.StrictRedis(host='localhost', port=6379, db=4)
api = twitter.Api(
    consumer_key        = secret.consumer_key, 
    consumer_secret     = secret.consumer_secret, 
    access_token_key    = secret.access_token_key, 
    access_token_secret = secret.access_token_secret
)

if sys.argv[1] == 'pull':
    count = 150

    statuses = api.GetHomeTimeline(count=count)
    print "Got your timeline"
    bar = Bar('Processing', max=count)
    for status in statuses:
        statusDict = status.AsDict()
        bar.next()

        try:
            filteredDict = getFilteredDict(statusDict)
            if 'retweeted_status' in statusDict:
                created_at = datetime.datetime.strptime(statusDict['retweeted_status']['created_at'], '%a %b %d %H:%M:%S +0000 %Y')
            else:
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
        tweetIds = r.keys('*')
        if len(sys.argv) == 2:
            tweets = []
            for tweetId in tweetIds:
                if r.hget(tweetId, 'like') == None:
                    tweets.append(tweetId)
        else:
            tweets = tweetIds
        return template('index', tweets=tweets)

    @route('/<id>')
    def tweet(id):
        like = r.hget(id, 'like')
        tweetId = id.split('_')[1]
        t = requests.get('https://api.twitter.com/1/statuses/oembed.json?url=https://twitter.com/Interior/status/'+tweetId)
        content = loads(t.text)
        content['like'] = like
        response.content_type = 'application/json'
        return dumps(content);

    @route('/<id>/<state>')
    def choice(id, state):
        if state == 'u':
            r.delete(id)
        else:
            r.hset(id, 'like', state)
        response.content_type = 'application/json'
        return dumps('ok');

    run(host='localhost', port=8081)

elif sys.argv[1] == 'train':
    now = datetime.datetime.now()
    trainIds = r.keys('%04d%02d*'%(now.year, now.month))
    trainSamples = []
    targetSamples = []
    for trainId in trainIds:
        trainRaw = r.hgetall(trainId)
        trainSample = convertToScikit(trainRaw)

        if 'like' in trainRaw:
            targetSamples.append(float(trainRaw['like']))
        else:
            targetSamples.append(float(0))

        trainSamples.append(trainSample)

    trainSamples  = np.array(trainSamples)
    targetSamples = np.array(targetSamples)
    
    sumScore = 0

    alg1 = LogisticRegression(random_state=1)
    predicted = cross_val_predict(alg1, trainSamples, targetSamples, cv=3)
    score = accuracy_score(targetSamples, predicted)
    print 'Logistic Regression : %f'%score.mean()
    sumScore += score.mean()
    alg1.fit(trainSamples, targetSamples)
    r2.set('LogisticRegression', pickle.dumps(alg1))

    alg2 = RandomForestClassifier(random_state=1, n_estimators=25, min_samples_split=4, min_samples_leaf=2)
    predicted = cross_val_predict(alg2, trainSamples, targetSamples, cv=3)
    score = accuracy_score(targetSamples, predicted)
    print 'Random Forest : %f'%score.mean()
    sumScore += score.mean()
    alg2.fit(trainSamples, targetSamples)
    r2.set('RandomForest', pickle.dumps(alg2))

    alg3 = GradientBoostingClassifier(random_state=1, n_estimators=25, max_depth=4)
    predicted = cross_val_predict(alg3, trainSamples, targetSamples, cv=3)
    score = accuracy_score(targetSamples, predicted)
    print 'Gradient Boosting : %f'%score.mean()
    sumScore += score.mean()
    alg3.fit(trainSamples, targetSamples)
    r2.set('GradientBoosting', pickle.dumps(alg3))

    alg4 = svm.SVC(random_state=1)
    predicted = cross_val_predict(alg4, trainSamples, targetSamples, cv=3)
    score = accuracy_score(targetSamples, predicted)
    print 'Support Vector : %f'%score.mean()
    sumScore += score.mean()
    alg4.fit(trainSamples, targetSamples)
    r2.set('SupportVector', pickle.dumps(alg4))

    alg5 = GaussianNB()
    predicted = cross_val_predict(alg5, trainSamples, targetSamples, cv=3)
    score = accuracy_score(targetSamples, predicted)
    print 'Gaussian Naive Bayes : %f'%score.mean()
    sumScore += score.mean()
    alg5.fit(trainSamples, targetSamples)
    r2.set('GaussianNaiveBayes', pickle.dumps(alg5))

    alg6 = MLPClassifier(algorithm='l-bfgs', alpha=1e-5, hidden_layer_sizes=(15, 4), random_state=1)
    predicted = cross_val_predict(alg6, trainSamples, targetSamples, cv=3)
    score = accuracy_score(targetSamples, predicted)
    print 'Perceptron : %f'%score.mean()
    sumScore += score.mean()
    alg6.fit(trainSamples, targetSamples)
    r2.set('Perceptron', pickle.dumps(alg6))

    print sumScore/6


elif sys.argv[1] == 'test':
    statuses = api.GetHomeTimeline(count=10)

    testSamples = []
    tweets = []
    for status in statuses:
        statusDict = status.AsDict()
        tweets.append(str(statusDict['id']))
        filteredDict = getFilteredDict(statusDict)
        testSample = convertToScikit(filteredDict)
        testSamples.append(testSample)

    testSamples = np.array(testSamples)
    algos = ['LogisticRegression', 'RandomForest', 'GradientBoosting', 'SupportVector', 'GaussianNaiveBayes', 'Perceptron']
    results = {}
    r2 = redis.StrictRedis(host='localhost', port=6379, db=4)

    for algo in algos:
        alg = pickle.loads(r2.get(algo))
        result = map(lambda x: int(x), alg.predict(testSamples))
        results.update({algo: result})

    @route('/')
    def index():
        return template('result', results=results, tweets=tweets)

    @route('/<id>')
    def tweet(id):
        t = requests.get('https://api.twitter.com/1/statuses/oembed.json?url=https://twitter.com/Interior/status/'+id)
        response.content_type = 'application/json'
        return t.text

    run(host='localhost', port=8081)
    





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
