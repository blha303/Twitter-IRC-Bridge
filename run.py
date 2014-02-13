import sys
import json
from time import sleep

import yaml
from twitter import *
from twisted.internet import reactor, task, protocol
from twisted.python import log
from twisted.words.protocols import irc
from twisted.application import internet, service


with open('config.yml') as configf:
    config = yaml.load(configf.read())
HOST, PORT = config['host'], config['port']


def munge(inp):
    return inp[0] + u"\u200b" + inp[1:]


def parsemsg(msg):
    for i in msg["entities"]["urls"]:
        msg["text"] = msg["text"].replace(i["url"], i["expanded_url"])
    return msg["text"]


class TwitterProtocol(irc.IRCClient):
    nickname = config["nickname"]
    username = 'Twitter'
    versionName = 'Twitter'
    versionNum = 'v1.6'
    realname = 'https://github.com/blha303/Twitter-IRCBridge'
    loopcall = None

    def __init__(self):
        self.lastid = {}
        try:
            with open('lastid') as f:
                self.lastid = json.loads(f.read())
        except (IOError, ValueError):
            with open('lastid', 'w') as f:
                f.write(json.dumps(self.lastid))
                print "Created lastid file"

    def updatelastid(self, sn, lid):
        self.lastid[sn] = lid
        with open('lastid', 'w') as f:
            f.write(json.dumps(self.lastid))

    def signedOn(self):
        for channel in self.factory.channels:
            self.join(channel)
        if config["nickserv"]:
            self._send_message("identify " + config["nickserv"], "NickServ")

        def restartloop(reason):
            reason.printTraceback()
            print "Loop crashed: " + reason.getErrorMessage()
            sleep(3)
            self.loopcall.start(60.0).addErrback(restartloop)
        self.loopcall = task.LoopingCall(self.getnewtweets)
        self.loopcall.start(60.0).addErrback(restartloop)

    def getnewtweets(self):
        print "Getting tweets."
        t = Twitter(auth=OAuth(config["oauth-token"],
                               config["oauth-secret"],
                               config["consumer-key"],
                               config["consumer-secret"]))
        for sn in config["twusers"]:
            print "Starting " + sn
            try:
                if sn in self.lastid:
                    print "[%s] lastid: %s" % (sn, self.lastid[sn])
                    timeline = t.statuses.user_timeline(screen_name=sn,
                                                        since_id=self.lastid[sn],
                                                        count=5,
                                                        exclude_replies=True)
                else:
                    timeline = t.statuses.user_timeline(screen_name=sn, count=5,
                                                        exclude_replies=True)
                timeline.reverse()
                for i in timeline:
                    fmt = u"\x02{screen_name}\x02: \x02{text}\x02 [ https://twitter.com/{screen_name}/status/{id} ]"
                    out = fmt.format(text=parsemsg(i),
                                     screen_name=sn,
                                     id=i["id_str"])
                    print "Sending " + out
                    try:
                        self._send_message(out.encode('utf-8'), config["twusers"][sn])
                    except UnicodeError:
                        print "Couldn't send %s due to error"
                    self.updatelastid(sn, i["id_str"])
            finally:
                print "Done " + sn
                print "----------"

    def privmsg(self, user, channel, message):
        nick, _, host = user.partition('!')
        try:
            key = (key for key, value in config["twusers"].items() if value.lower() == channel.lower()).next()
        except StopIteration:
            key = None
        split = message.split(" ")
        if message == "!twitter":
            if key:
                self._send_message("https://twitter.com/" + key, channel)
            else:
                self._send_message("I'm not set up for this channel.", channel)
        elif split[0] == "!add" and nick == config["owner"]:
            if len(split) != 3:
                self._send_message("Usage: !add screenname #channel", channel)
            else:
                config["twusers"][split[1]] = split[2]
                with open('config.yml', 'w') as f:
                    f.write(yaml.dump(config))
                self.join(split[2])
                self._send_message("Hi! I'm here to relay messages from https://twitter.com/%s to this "
                                   "channel. Please ask %s if you have any questions or would like"
                                   "this bot removed." % (config["owner"], split[1]), split[2])
                self._send_message("Done.", channel)
        elif split[0] == "!del" and nick == config["owner"]:
            if len(split) != 2:
                self._send_message("Usage: !del #channel", channel)
            else:
                try:
                    del config["twusers"][key]
                    self.leave(split[1])
                    with open('config.yml', 'w') as f:
                        f.write(yaml.dump(config))
                except StopIteration:
                    self._send_message("I'm not set up for that channel.", channel)

    def _send_message(self, msg, target, nick=None):
        if nick:
            msg = '%s, %s' % (nick, msg)
        self.msg(target, msg)

    @staticmethod
    def _show_error(failure):
        return failure.getErrorMessage()


class TwitterFactory(protocol.ReconnectingClientFactory):
    protocol = TwitterProtocol
    channels = config["twusers"].values()

if __name__ == '__main__':
    reactor.connectTCP(HOST, PORT, TwitterFactory())
    log.startLogging(sys.stdout)
    reactor.run()

elif __name__ == '__builtin__':
    application = service.Application('Twitter')
    ircService = internet.TCPClient(HOST, PORT, TwitterFactory())
    ircService.setServiceParent(application)
