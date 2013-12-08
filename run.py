import sys
import re
import urllib2
import json
import random
import unicodedata
import yaml
import ago
from twitter import *
from dateutil.parser import parse
from twisted.internet import reactor, task, defer, protocol
from twisted.python import log
from twisted.words.protocols import irc
from twisted.web.client import getPage
from twisted.application import internet, service

with open('config.yml') as f:
    config = yaml.load(f.read())
HOST, PORT = config['host'], config['port']


def munge(inp):
    return inp[0] + u"\u200b" + inp[1:]


def localTzname():
    offsetHour = time.timezone / 3600
    return 'Etc/GMT%+d' % offsetHour


class HeadRequest(urllib2.Request):
        def get_method(self):
            return "HEAD"


class TwitterProtocol(irc.IRCClient):
    nickname = 'Twitter'
    username = 'Twitter'
    versionName = 'Twitter'
    versionNum = 'v1.1'
    realname = 'https://github.com/blha303/IRCCloud-TwitterBridge'
    loopcall = None
    lastid = None
    lasttweet = None
    ratelimitstatus = None
    channel = ""
    try:
        with open('lastid') as f:
            lastid = f.read()
    except:
        with open('lastid', 'w') as f:
            print "Created lastid file"
#    try:
#        with open('lasttweet') as f:
#            lasttweet = json.loads(f.read())
#    except:
#        with open('lasttweet', 'w') as f:
#            print "Created lasttweet file"


    def updateLastid(self, id):
        self.lastid = id
        with open('lastid', 'w') as f:
            f.write(id)


    def parsemsg(self, msg):
        for i in msg["entities"]["urls"]:
            msg["text"] = msg["text"].replace(i["url"], i["expanded_url"])
        return msg["text"]


    def updateLasttweet(self, tweet):
        print "in updateLasttweet"
        self.lasttweet = tweet
        print "set self.lasttweet"
        with open('lasttweet', 'w') as f:
            print "opened lasttweet"
            f.write(json.dumps(tweet))
            print "written lasttweet"


    def signedOn(self):
        self.channel = self.factory.channels[0]
        for channel in self.factory.channels:
            self.join(channel)
        self._send_message("identify " + config["nickserv"], "NickServ")

        def restartloop(reason):
            reason.printTraceback()
            print "Loop crashed: " + reason.getErrorMessage()
            self.loopcall.start(60.0).addErrback(restartloop)
        self.loopcall = task.LoopingCall(self.getNewTweets)
        self.loopcall.start(60.0).addErrback(restartloop)

    def getNewTweets(self):
        print "Getting tweets."
        try:
            t = Twitter(auth=OAuth(config["oauth-token"],
                                   config["oauth-secret"],
                                   config["consumer-key"],
                                   config["consumer-secret"]))
            if self.lastid:
                print "lastid: " + self.lastid
                timeline = t.statuses.user_timeline.irccloud(
                    since_id=self.lastid, count=5, exclude_replies=True)
            else:
                timeline = t.statuses.user_timeline.irccloud(count=5,
                                                               exclude_replies=True)
            timeline.reverse()
            for i in timeline:
                fmt = u"{text} https://twitter.com/irccloud/status/{id}"
#                username = i["user"]["screen_name"]
#                timeago = ago.human(parse(i["created_at"]))
                out = fmt.format(text=self.parsemsg(i),
                                 id=i["id_str"])
                print "Sending " + out
                self._send_message(out.encode('utf-8'), self.channel)
                self.updateLastid(i["id_str"])
#                self.updateLasttweet(i)
#            if not self.lasttweet:
#                print "self.lasttweet doesn't have content! fixing."
#                tweet = t.statuses.user_timeline.irccloud(count=1, exclude_replies=True)[0]
#                print tweet.keys()
#                self.updateLasttweet(tweet)
            print "We're done here."
            print "----------"
        finally:
            return

    def privmsg(self, user, channel, message):
        nick, _, host = user.partition('!')
        if message == "!update" and nick == "blha303":
            self.getNewTweets()
        elif message == "!twitter":
            if self.lasttweet:
                i = self.lasttweet
            else:
                self._send_message("No last tweet available. Weird. blha303, what's going on?", self.channel)
                return
            fmt = u"{text} ({timeago}) https://twitter.com/irccloud/status/{id}"
            username = i["user"]["screen_name"]
            timeago = ago.human(parse(i["created_at"]))
            out = fmt.format(text=self.parsemsg(i["text"]),
                             timeago=timeago,
                             id=i["id_str"])
            self._send_message(out.encode('utf-8'), self.channel)


    def _send_message(self, msg, target, nick=None):
        if nick:
            msg = '%s, %s' % (nick, msg)
        self.msg(target, msg)

    def _show_error(self, failure):
        return failure.getErrorMessage()


class TwitterFactory(protocol.ReconnectingClientFactory):
    protocol = TwitterProtocol
    channels = ['#twittertest']

if __name__ == '__main__':
    reactor.connectTCP(HOST, PORT, TwitterFactory())
    log.startLogging(sys.stdout)
    reactor.run()

elif __name__ == '__builtin__':
    application = service.Application('Twitter')
    ircService = internet.TCPClient(HOST, PORT, TwitterFactory())
    ircService.setServiceParent(application)
