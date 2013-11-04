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


class TwitterProtocol(irc.IRCClient):
    nickname = 'Twitter'
    username = 'Twitter'
    versionName = 'Twitter'
    versionNum = 'v1.0'
    realname = 'blha303'
    loopcall = None
    lastid = None
    channel = ""
    try:
        with open('lastid') as f:
            lastid = f.read()
    except:
        with open('lastid', 'w') as f:
            print "Created lastid file"


    def updateLastid(self, id):
        self.lastid = id
        with open('lastid', 'w') as f:
            f.write(id)


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
                    since_id=self.lastid, count=5)
            else:
                timeline = t.statuses.user_timeline.irccloud(count=5)
            timeline.reverse()
            for i in timeline:
                if i["text"][0] == "@":
                    continue
                fmt = u"{name} (@{screen_name}): {text} ({timeago})"
                username = i["user"]["screen_name"]
                timeago = ago.human(parse(i["created_at"]))
                out = fmt.format(name=munge(i["user"]["name"]),
                                 screen_name=munge(username),
                                 text=i["text"],
                                 timeago=timeago)
                print "Sending " + out
                self._send_message(out.encode('utf-8'), self.channel)
                self.updateLastid(i["id_str"])
            print "We're done here."
            print "----------"
        finally:
            return

    def privmsg(self, user, channel, message):
        nick, _, host = user.partition('!')
        message = message

    def _send_message(self, msg, target, nick=None):
        if nick:
            msg = '%s, %s' % (nick, msg)
        self.msg(target, msg)

    def _show_error(self, failure):
        return failure.getErrorMessage()


class TwitterFactory(protocol.ReconnectingClientFactory):
    protocol = TwitterProtocol
    channels = ['#feedback']

if __name__ == '__main__':
    reactor.connectTCP(HOST, PORT, TwitterFactory())
    log.startLogging(sys.stdout)
    reactor.run()

elif __name__ == '__builtin__':
    application = service.Application('Twitter')
    ircService = internet.TCPClient(HOST, PORT, TwitterFactory())
    ircService.setServiceParent(application)
