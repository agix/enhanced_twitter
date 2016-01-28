# enhanced_twitter
Enhanced twitter experience with machine learning

## Requirements

* `pip install python-twitter`
* `pip install requests`
* `pip install bottle`
* `pip install redis`
* `pip install progress`
* `pip install numpy`
* `pip install scikit-learn`
 
Download redis http://redis.io/download

Create `secret.py` :
```
consumer_key        = 'bla'
consumer_secret     = 'bla2'
access_token_key    = 'bla3' 
access_token_secret = 'bla4'
```

## Usage
`Usage: python twittor.py <pull|qualify|train|test>`

* `pull` to pull the last 100 tweets from your timeline
* `qualify` run a mini webserver -> http://localhost:8081/ to let you qualify your tweets
* `train` TODO
* `test` run a mini webserver -> http://localhost:8081/ show result for 10 new tweets
