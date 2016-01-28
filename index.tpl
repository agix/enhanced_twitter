<script src="//platform.twitter.com/widgets.js" charset="utf-8"></script>
<style>
#currentTweet iframe{
    margin:auto;
}
</style>
<body style="text-align:center">
<h1>Twittor</h1>
<div id="currentTweet"></div>
<div style="display:inline;">
    <button id="previous">&lt;- Previous</button>
    <button id="good">GOOD</button>
    <button id="notgood">NOTGOOD</button>
    <button id="next">Next -&gt;</button>
</div>
<script>
var id = 0;
var tweets = {{!tweets}};

document.addEventListener("DOMContentLoaded", function(event) { 

    getTweet(tweets[id]);

    twttr.events.bind(
        'loaded',
        function (event) {
            console.log('boom');
            if(document.getElementById('good').style.fontSize === '15px'){
                document.getElementById('currentTweet').children[0].style.border = '1px solid green';
            }
            else if(document.getElementById('notgood').style.fontSize === '15px'){
                document.getElementById('currentTweet').children[0].style.border = '1px solid red';
            }
            else{
                document.getElementById('currentTweet').children[0].style.border = '1px solid grey';
            }
        }
    );
});

function GET(url, cb){
    var request = new XMLHttpRequest();
    request.open('GET', '/'+url, true);

    request.onload = function() {
      if (request.status >= 200 && request.status < 400) {
        // Success!
        var data = JSON.parse(request.responseText);
        cb(data);
      } else {
        // We reached our target server, but it returned an error

      }
    };

    request.onerror = function() {
      // There was a connection error of some sort
    };

    request.send();
}

function getTweet(tweet){
    GET(tweet, function(data){
        var currentTweet = document.getElementById('currentTweet');
        currentTweet.innerHTML = data.html;
        twttr.widgets.load(currentTweet);

        if(data.like === '1'){
            document.getElementById('good').style.fontSize = 15;
            document.getElementById('notgood').style.fontSize = 13;
        }
        else if(data.like === '0'){
            document.getElementById('notgood').style.fontSize = 15;
            document.getElementById('good').style.fontSize = 13;
        }
        else{
            document.getElementById('notgood').style.fontSize = 13;
            document.getElementById('good').style.fontSize = 13;
        }
    });
}


document.getElementById('good').onclick = function(event){
    GET(tweets[id]+'/1', function(){
        getTweet(tweets[id]);
    });
}

document.getElementById('notgood').onclick = function(event){
    GET(tweets[id]+'/0', function(){
        getTweet(tweets[id]);
    });
}

document.onkeydown = function(event) {
    var keyPressed;

    if (event === null) {
        keyPressed = window.event.keyCode;
    } else {
        keyPressed = event.keyCode;
    }
    keyPress(keyPressed);

}

function keyPress(keyPressed){
    switch (keyPressed) {
        case 37:
            //left
            if(id === 0){
                id = tweets.length-1;
            }
            else{
                id -= 1;
            }
            break;
        case 39:
            //right
            if(id === tweets.length-1){
                id = 0;
            }
            else{
                id += 1;
            }
            break;
    }
    if(keyPressed === 37 || keyPressed === 39){
        getTweet(tweets[id]);
    }
}

document.getElementById('previous').onclick = function(event){
    keyPress(37);
}

document.getElementById('next').onclick = function(event){
    keyPress(39);
}
    

</script>
</body>