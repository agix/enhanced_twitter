import twitter
import requests
import redis
import sys
from bottle import route, run, template, response
from json import dumps, loads
import secret

if len(sys.argv) != 2:
    print 'Usage: %s <pull|qualify|train>'
    sys.exit(0)

r = redis.StrictRedis(host='localhost', port=6379, db=3)

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
                'retweeted'         : statusDict['retweeted'],
                'favorited'         : statusDict['favorited'],
                'lang'              : statusDict['lang'],
                'origuserProtected' : statusDict['user']['protected'],
                'origuserLang'      : statusDict['user']['lang'],
                'origuserId'        : statusDict['user']['id'],
                'origuserVerified'  :'verified' in statusDict['user']
            }

            if 'followers_count' in statusDict:
                filteredDict['origuserFollowers_count'] = statusDict['followers_count']
            else:
                filteredDict['origuserFollowers_count'] = 0
            if 'friends_count' in statusDict:
                filteredDict['origuserFriends_count'] = statusDict['friends_count']
            else:
                filteredDict['origuserFriends_count'] = 0
                
            if 'retweeted_status' in statusDict:
                filteredDict['retweeted_status'] = 1
                if 'favorite_count' in statusDict['retweeted_status']:
                    filteredDict['favorite_count'] = statusDict['retweeted_status']['favorite_count']
                else:
                    filteredDict['favorite_count'] = 0
                if 'retweet_count' in statusDict['retweeted_status']:
                    filteredDict['retweet_count'] = statusDict['retweeted_status']['retweet_count']
                else:
                    filteredDict['retweet_count'] = 0

                if 'followers_count' in statusDict['retweeted_status']:
                    filteredDict['userFollowers_count'] = statusDict['retweeted_status']['followers_count']
                else:
                    filteredDict['userFollowers_count'] = 0
                if 'friends_count' in statusDict['retweeted_status']:
                    filteredDict['userFriends_count'] = statusDict['retweeted_status']['friends_count']
                else:
                    filteredDict['userFriends_count'] = 0
                
                filteredDict['userProtected'] = statusDict['retweeted_status']['user']['protected']
                filteredDict['userLang'] = statusDict['retweeted_status']['user']['lang']
                filteredDict['userId'] = statusDict['retweeted_status']['user']['id']
                filteredDict['userVerified'] = 'verified' in statusDict['retweeted_status']['user']
            else:
                filteredDict['retweeted_status'] = 0
                if 'favorite_count' in statusDict:
                    filteredDict['favorite_count'] = statusDict['favorite_count']
                else:
                    filteredDict['favorite_count'] = 0
                if 'retweet_count' in statusDict:
                    filteredDict['retweet_count'] = statusDict['retweet_count']
                else:
                    filteredDict['retweet_count'] = 0

                if 'followers_count' in statusDict:
                    filteredDict['userFollowers_count'] = statusDict['followers_count']
                else:
                    filteredDict['userFollowers_count'] = 0
                if 'friends_count' in statusDict:
                    filteredDict['userFriends_count'] = statusDict['friends_count']
                else:
                    filteredDict['userFriends_count'] = 0

                filteredDict['userProtected'] = statusDict['user']['protected']
                filteredDict['userLang'] = statusDict['user']['lang']
                filteredDict['userId'] = statusDict['user']['id']
                filteredDict['userVerified'] = 'verified' in statusDict['user']
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