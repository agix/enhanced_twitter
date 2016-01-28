# enhanced_twitter
Enhanced twitter experience with machine learning

## Requirements

* `pip install python-twitter`
* `pip install requests`
* `pip install bottle`
* `pip install redis`
 
Download redis http://redis.io/download

Create secret.py :
```
consumer_key        = 'bla'
consumer_secret     = 'bla2'
access_token_key    = 'bla3' 
access_token_secret = 'bla4'
```

## Usage
Usage: python twittor.py <pull|qualify|train>

* `pull` to pull the last 200 tweets from your timeline
* `qualify` run a mini webserver -> http://localhost:8081/ and qualify your tweets
* `train` TODO
