#!/usr/bin/python
#-*- coding: utf-8 -*-
#
# Copyright 2006 Develer S.r.l. (http://www.develer.com/)
# All rights reserved.
#
# $Id:$
#
# Author: Matteo Bertini <naufraghi@develer.com>
#

import urllib, urllib2, urlparse
from pyuac_utils import *
import saml_ecp

ACHIEVO_ENCODING = "ISO-8859-15"

# True se vogliamo autenticarci con SAML su Achievo
USE_SAML = True

# Indirizzo dell'IDP SAML di Develer 
DEVELER_IDP = "https://login.develer.com/saml2/idp/SSOService.php"


class RemoteTimereg:
    """
    RemoteTimereg si interfaccia (in modo sincrono) con il modulo Achievo "remote".
    Sia server che client sono fondamentalmente stateles, l'unico stato è
    l'aver fatto login, condizione obbligatoria per compiere qualsiasi funzione.
    I metodi accettano parametri standard e restituiscono un oggetto ElementTree.
    """

    actions = {"login": "Log into an Achievo server (uri, user, pwd)",
               "query": "Search the project matching the smartquery",
               "whoami": "Returns login info",
               "timereg": "Register worked time",
               "delete": "Delete the timered by id",
               "timereport": "Report time registered in the provided date[s]"}

    def __init__(self):
        self._smartquery_dict = parseSmartQuery("")
        self._projects = ET.fromstring("<response />")
        self._login_done = False
        self._auth_done = False

    def login(self, achievouri, user, password):
        """
        Classe di interfaccia per il modulo Achievo "remote"
        Fornire la path di achievo, username e password
        Restituisce il nome utente e rinfresca la sessione di Achievo
        """
        self.user = user
        self.userid = 0
        self.version = None
        self.password = password
        self._achievouri = achievouri
        self._loginurl = urllib.basejoin(self._achievouri, "index.php")
        self._dispatchurl = urllib.basejoin(self._achievouri, "dispatch.php")
        self._keepalive()
        self._login_done = True
        return self.whoami()

    def _keepalive(self):
        """
        Restituisce il nome utente e rinfresca la sessione di Achievo
        """
        # Renew Achievo login to keep the session alive
        auth = urllib.urlencode({"auth_user": self.user,
                                 "auth_pw": self.password})
        if not self._auth_done:
            self._setupAuth()
        # refresh Achievo session
        urllib2.urlopen(self._loginurl, auth).read()

    def _setupAuth(self):
        """
        Imposta l'autenticazione http e la gestione dei cookies
        """
        if USE_SAML:
            opener = saml_ecp.auth(DEVELER_IDP, self._achievouri, self.user, self.password)
            urllib2.install_opener(opener)
        else:
            passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
            # WARN: basic-auth using a URI which is not a pure hostname is
            # broken in Python 2.4.[0123]. This patch fixed it:
            # http://svn.python.org/view/python/trunk/Lib/urllib2.py?rev=45815&r1=43556&r2=45815
            host = urlparse.urlparse(self._achievouri)[1]
            passman.add_password(None, host, self.user, self.password)
            auth_handler = urllib2.HTTPBasicAuthHandler(passman)
            cookie_handler = urllib2.HTTPCookieProcessor()
            opener = urllib2.build_opener(auth_handler, cookie_handler)
            urllib2.install_opener(opener)
        self._auth_done = True

    def _urlDispatch(self, node, action="search", **kwargs):
        """
        Invoca il dispatch.php di Achievo
        """
        params = {"atknodetype": "remote.%s" % node,
                  "atkaction": action}
        # This is the way PHP accepts arrays,
        # without [] it gets only the last value.
        for key, val in kwargs.items():
            if type(val) == list:
                del kwargs[key]
                kwargs[key+"[]"] = [v.encode(ACHIEVO_ENCODING, "replace") for v in val]
            else:
                kwargs[key] = val.encode(ACHIEVO_ENCODING, "replace")
        qstring = urllib.urlencode(params.items() + kwargs.items(), doseq=True)
        if __debug__:
            debug("%s?%s" % (self._dispatchurl, qstring))
        page = urllib2.urlopen(self._dispatchurl, qstring).read().strip()
        try:
            return ET.fromstring(page)
        except Exception:
            debug(page.decode(ACHIEVO_ENCODING))
            raise Exception, page.decode(ACHIEVO_ENCODING)

    def whoami(self):
        """
        Restituisce il nome utente della sessione attiva
        """
        elogin = self._urlDispatch("whoami")
        if self.userid == 0:
            self.userid = elogin[0].get("id")
        if self.version == None:
            self.version = elogin[0].get("version", "1.2.1")
        return elogin

    def query(self, smartquery):
        """
        Ottiene la lista dei progetti/fasi/attività coerenti
        con la smart-string inviata, restituisce un ElementTree
        """
        self._projects = self._urlDispatch("query", input=smartquery)

        for p in self._projects[:1]:
            #TODO: move serverside using Achievo funcs
            hmtime = p.get("in_hmtime")
            if hmtime:
                if ":" not in hmtime:
                    hmtime = "%s:00" % hmtime
                if len(hmtime.split(":")[0]) < 2:
                    hmtime = "0%s" % hmtime
                if len(hmtime.split(":")[1]) < 2:
                    hmtime = "%s:%02d" % (hmtime.split(":")[0], int(hmtime.split(":")[1] or "0"))
                if hmtime2min(hmtime) < hmtime2min("24:00"):
                    hmtime = timeRound(hmtime)
            else:
                hmtime = ""
            p.set("hmtime", hmtime)
        return self._projects

    def timereport(self, date):
        """
        Ottiene la lista delle ore registrate nei giorni
        passati nel parametro date
        """
        return self._urlDispatch("timereport", date=date)

    def timesummary(self, date_start, date_end):
        """
        Ottiene la lista delle ore registrate nei giorni
        compresi nell'intervallo date_start <= date <= date_end
        """
        return self._urlDispatch("timesummary", date_start=date_start, date_end=date_end)

    def timereg(self, projectid, activityid, phaseid, hmtime, activitydate, remark, id=None):
        """
        Registra un blocco di ore lavorate
        """
        kwargs = {"projectid": "project.id=%s" % projectid,
                  "activityid": "activity.id=%s" % activityid,
                  "phaseid": "phase.id=%s" % phaseid,
                  "time[hours]": hmtime.split(":")[0],
                  "time[minutes]": hmtime.split(":")[1],
                  "activitydate[year]": activitydate.split("-")[0],
                  "activitydate[month]": activitydate.split("-")[1],
                  "activitydate[day]": activitydate.split("-")[2],
                  "entrydate[year]": time.strftime("%Y", time.gmtime()),
                  "entrydate[month]": time.strftime("%m", time.gmtime()),
                  "entrydate[day]": time.strftime("%d", time.gmtime()),
                  "remark": remark,
                  "userid": "person.id=%s" % self.userid}
        ver = lambda v: map(int, v.split("."))
        if ver(self.version) < ver("1.3.0"):
            kwargs.update({"projectid": projectid,
                           "activityid": activityid,
                           "phaseid": phaseid})
        #TODO: The server should get the userid from the current session
        if id == None: # save new record
            epage = self._urlDispatch("timereg", action="save", **kwargs)
        else: # update
            kwargs["id"] = id
            kwargs["atkprimkey"] = "hours.id='%s'" % id
            #TODO: find out which is the one used by Achievo
            epage = self._urlDispatch("timereg", action="edit", **kwargs)
        #sys.stderr.write("%s: %s\n" % ("timereg", kwargs))
        return epage

    def delete(self, id):
        kwargs = {"atkselector": "hoursbase.id=%s" % id,
                  "confirm": "Yes"}
        epage = self._urlDispatch("timereg", action="delete", **kwargs)
        return epage

example_save = """
curl -v -b cookie -c cookie \
        -d auth_user=matteo -d auth_pw=matteo99 \
        http://www.develer.com/~naufraghi/achievo/index.php

curl -v -b cookie -c cookie \
-d atknodetype=remote.timereg \
-d atkaction=save \
-d activityid=2 \
-d projectid=6 \
-d phaseid=6 \
-d time[hours]=5 \
-d time[minutes]=15 \
-d activitydate=20061117 \
-d entrydate=20061117 \
-d remark=remarkfoo%20popo%20popop%20opopop \
-d userid=person.id=1 \
http://www.develer.com/~naufraghi/achievo/dispatch.php

curl -v -b cookie -c cookie \
        http://www.develer.com/~naufraghi/achievo/index.php?atklogout=1
"""

example_edit = """
https://www.develer.com/groupware/dispatch.php?
atklevel=3&
atkprevlevel=2&
atkstackid=4e31a43913bfe&
achievo=7tig5dkq0a8eat2027fuf6u883&
atkescape=&
#atkaction=update&
atkprevaction=edit&
atkfieldprefix=&
#atknodetype=timereg.hours&
#atkprimkey=hoursbase.id%3D%2753518%27&
dayfilter=&
#id=53518&
virtual_time=0&
#userid=person.id%3D%2732%27&
#entrydate[year]=2011&
#entrydate[month]=07&
#entrydate[day]=28&
#activitydate[day]=27&
#activitydate[month]=7&
#activitydate[year]=2011&
#projectid=project.id%3D%2740%27&
#phaseid=phase.id%3D%27152%27&
#activityid=activity.id%3D%273%27&
#remark=Convex+Hull%2C+Specchiate+e+piazzamento+invalido&
#time[hours]=8&
#time[minutes]=45&
atknoclose=Save
"""

if __name__ == "__main__":
    rl = RemoteTimereg()
    rl.login("https://www.develer.com/~naufraghi/achievo_modstats/", "matteo", "demo")
    print ET.tostring(rl.whoami())
    rl.query("pr")
    rl.query("pr me")
    rl.query("pr me an")
    rl.timereport("2006-11-7")
    rl.timereport(["2006-11-7", "2006-11-8"])
