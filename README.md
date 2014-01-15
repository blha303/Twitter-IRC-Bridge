Twitter-IRC-Bridge
=================
 
* Get Virtualenv
* Use `virtualenv venv -p python2.7`
* Use `venv/bin/pip install -r requirements.txt`
* Copy `configsample.yml` to `config.yml`
* Create a new Twitter application at https://dev.twitter.com/apps/new
* Click on Create Access Token at the bottom of the app summary page and refresh every five seconds until the Access Token comes up
* Copy the Access Token and Consumer keys (above) into config.yml
* Change the network/channel/screen_name options
* Use `venv/bin/twistd -y run.py`
* [Let me know if there's any problems](https://github.com/blha303/Twitter-IRC-Bridge/issues) (or irc.freenode.net #blha303)
