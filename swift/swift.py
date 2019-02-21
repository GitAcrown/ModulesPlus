import asyncio
import os
import random
import re
import time
from urllib.parse import unquote

import aiohttp
import discord
import wikipedia
import wikipediaapi
from __main__ import send_cmd_help
from discord.ext import commands

from .utils import checks
from .utils.dataIO import fileIO, dataIO


class SwiftAPI:
    """API de Swift - Assistant personnel fourni par Turing"""
    def __init__(self, bot, path):
        self.bot = bot
        self.data = dataIO.load_json(path)
        self.meta = {"last_save": 0}

    def save(self, force: bool = False):
        if force:
            fileIO("data/swift/data.json", "save", self.data)
        elif (time.time() - self.meta["last_save"]) >= 120: # 2 minutes
            fileIO("data/swift/data.json", "save", self.data)
            self.meta["last_save"] = time.time()

    def get_member(self, user: discord.Member):
        """Renvoie le profil Swift du membre"""
        if user.id not in self.data:
            self.data[user.id] = {"IGNORE": False,
                                  "NOTIFS": {}}
            self.save()
        return self.data[user.id]

class Swift:
    """L'Assistant personnel embarqué par Turing - Pour vous servir"""

    def __init__(self, bot):
        self.bot = bot
        self.swf = SwiftAPI(bot, "data/swift/data.json")
        self.sys = dataIO.load_json("data/swift/sys.json")
        self.context = {"last_save": 0, "servers": {}, "vuemoji": None}
        self.session = aiohttp.ClientSession()
        self.rgpd = "Turing exploite par le biais de différents modules vos données dans le but de vous offrir " \
                    "divers services. Ces données proviennent d'une part de Discord et d'autre part de l'analyse de " \
                    "vos messages et de votre présence sur les différents serveurs.\n" \
                    "Conformément au **Règlement Général sur la Protection des Données** ou **RGPD**, vous trouverez " \
                    "ci-dessous les différentes données que les modules sont susceptible d'exploiter et le but de " \
                    "cette action :\n\n" \
                    "**1°) Analyser 24h/24 et 7j/7 vos messages et réactions** afin de proposer divers services " \
                    "de statistiques, de modération ou plus globalement qui ont pour but de vous assister de " \
                    "différentes façons. Sauf indication contraire dans l'intitulé de la commande (`.help`) ou du " \
                    "service, ces messages ne sont pas sauvegardés.\n" \
                    "**2°) Surveiller les changements apportés à votre profil, votre statut, les jeux auxquels vous " \
                    "jouez etc.** afin de personnaliser votre expérience et toujours dans l'optique de statistiques ou" \
                    "de modération.\n" \
                    "**3°) Mettre en mémoire sur un serveur distant ces données**, que ceux-ci aient été directement " \
                    "fournis par l'utilisateur ou constituant le résultat d'une extraction de données (voir 2°). Sauf " \
                    "indication contraire dans l'intitulé de la commande (`.help`) ou du service, ces données ne sont" \
                    " en aucun cas cryptés bien que se trouvant sur un serveur privé dont le propriétaire est " \
                    "<@172376505354158080>.\n" \
                    "**4°) Garder des traces de votre présence même en votre absence.** Si vous quittez le serveur, " \
                    "les différentes données sauvegardées seront conservés mais, sauf en cas d'indication contraire, ne" \
                    " seront exploitable en votre absence. Dans certains cas, les mêmes données peuvent être utilisés " \
                    "par plusieurs serveurs distincts.\n\n" \
                    "Turing n'étant théoriquement pas contraint au RGPD, ces informations n'ont qu'une valeur indicative. " \
                    "De ce fait, la seule présence de Turing sur votre serveur vaut consentement.\n" \
                    "Pour toute réclamation, contactez <@172376505354158080>."

    def __unload(self):
        self.session.close()

    def sys_save(self, force: bool = False):
        if force:
            fileIO("data/swift/sys.json", "save", self.sys)
        elif (time.time() - self.context["last_save"]) >= 60: # une minute
            fileIO("data/swift/sys.json", "save", self.sys)
            self.context["last_save"] = time.time()

    def get_context(self, server: discord.Server):
        """Renvoie le contexte de la session Swift sur le serveur"""
        if server.id not in self.context["servers"]:
            self.context["servers"][server.id] = {"AFK": {},
                                                  "CITATIONS": {},
                                                  "SPOILS": {}}
        return self.context["servers"][server.id]

    def get_server(self, server: discord.Server, update_services: bool = False):
        """Renvoie les données Swift du serveur"""
        if server.id not in self.sys:
            self.sys[server.id] = {"SERVICES": {"repost": True,
                                                "afk": True,
                                                "msgchrono": True,
                                                "spoil": True,
                                                "quote": True,
                                                "reddit": True,
                                                "annexes": {}},
                                   "CACHE": {"repost": []},
                                   "ACTIF": False}
            fileIO("data/swift/sys.json", "save", self.sys)
        if update_services:
            for service in ["noelshack", "mobiletwitter", "subreddit", "ia_wikipedia", "mediagif"]:
                if service not in self.sys[server.id]["SERVICES"]["annexes"]:
                    self.sys[server.id]["SERVICES"]["annexes"][service] = True
            self.sys_save()
        return self.sys[server.id]


    # GREFFONS <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

    def redux(self, string: str, separateur: str = ".", limite: int = 2000):
        n = -1
        while len(separateur.join(string.split(separateur)[:n])) >= limite:
            n -= 1
        return separateur.join(string.split(separateur)[:n]) + separateur

    async def _wikipedia(self, message: discord.Message):
        """Traite la demande de recherche Wikipedia"""
        if self.get_server(message.server)["SERVICES"]["annexes"].get("ia_wikipedia", True):
            output = re.compile(r"(?:re)?cherche (.*)", re.IGNORECASE | re.DOTALL).findall(message.content)
            if output:
                await self.bot.send_message(message.channel, "*Note : les expressions `cherche X` et `recherche X` vont"
                                                            " bientôt tomber en désuétude, il est conseillé d'utiliser "
                                                            "`c'est quoi X` ou `qu'est-ce que X`*")
            else:
                output = re.compile(r"(?:est[- ](?:ce\s)?qu(?:oi|e))(.*)", re.IGNORECASE | re.DOTALL).findall(message.content)
            if output:
                langue = 'fr'
                search = output[0]
                wikipedia.set_lang(langue)
                wiki = wikipediaapi.Wikipedia(langue)
                while True:
                    await self.bot.send_typing(message.channel)
                    page = wiki.page(search)
                    if page.exists():
                        simil = wikipedia.search(search, 6, True)
                        txtsimil = ""
                        if simil:
                            if len(simil[0]) > 1:
                                txtsimil = "Résultats similaires • " + ", ".join(simil[0][1:])
                        txt = self.redux(page.summary)
                        if len(txt) == 1:
                            txt = "*Cliquez sur le titre pour accéder à la page d'homonymie*"
                        em = discord.Embed(title=page.title, description=txt, color=0xeeeeee, url=page.fullurl)
                        em.set_footer(text=txtsimil,
                                      icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Wikipedia-"
                                               "logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png")
                        msg = random.choice(["Voici ce que j'ai trouvé :", "Voilà :", "Voilà pour vous :", "Tout de suite :",
                                             "J'ai trouvé ça :"])
                        await self.bot.send_message(message.channel, msg, embed=em)
                        return True
                    elif langue == 'en':
                        wikipedia.set_lang('fr')
                        search = wikipedia.search(search, 8, True)[0]
                        if search:
                            ltxt = ""
                            liste = []
                            n = 1
                            for i in search:
                                liste.append([n, i])
                                n += 1
                            for _ in liste:
                                ltxt += "**{}** • {}\n".format(_[0], _[1].capitalize())
                            em = discord.Embed(title="Pages suggérées", description=ltxt, color=0xeeeeee)
                            msg = random.choice(["Je n'ai rien trouvé en particulier...",
                                                 "Désolé mais je n'ai rien trouvé avec ce nom...",
                                                 "Je ne peux que vous proposer des pages similaires.",
                                                 "Je suis désolé mais je n'ai trouvé que ça :"])
                            rdfot = random.choice(
                                ["Que vouliez-vous exactement ?", "Quelle était votre recherche dans cette liste ?",
                                 "Quel sujet est le bon ?", "Voulez-vous bien m'indiquer la bonne page à charger ?"])
                            em.set_footer(text=rdfot)
                            msg = await self.bot.send_message(message.channel, msg, embed=em)
                            rep = await self.bot.wait_for_message(channel=message.channel,
                                                                  author=message.author,
                                                                  timeout=10)
                            if rep is None:
                                await self.bot.delete_message(msg)
                                return True
                            elif rep.content.lower() in ["rien", "nvm", "nevermind", "stop", "merci",
                                                         "ca sera tout", "ça sera tout", "non merci"]:
                                poli = random.choice(["Bien entendu.", "D'accord, entendu.", "Très bien."])
                                await self.bot.send_message(message.channel, poli)
                                await self.bot.delete_message(msg)
                                return True
                            elif rep.content.lower() in [l.lower() for l in search]:
                                search = rep.content
                                await self.bot.delete_message(msg)
                            elif int(rep.content) in [i[0] for i in liste]:
                                search = False
                                for i in liste:
                                    if int(rep.content) == i[0]:
                                        search = i[1]
                                        break
                                await self.bot.delete_message(msg)
                                if not search:
                                    await self.bot.send_message(message.channel, "Aucun résulat.")
                                    return
                            else:
                                await self.bot.delete_message(msg)
                                return True
                        else:
                            wikipedia.set_lang('en')
                            search = wikipedia.search(search, 8, True)[0]
                            if search:
                                ltxt = ""
                                liste = []
                                n = 1
                                for i in search:
                                    liste.append([n, i])
                                    n += 1
                                for _ in liste:
                                    ltxt += "**{}** • {}\n".format(_[0], _[1].capitalize())
                                em = discord.Embed(title="Pages suggérées (en Anglais)", description=ltxt, color=0xeeeeee)
                                msg = random.choice(["Je n'ai rien trouvé en particulier...",
                                                     "Désolé mais je n'ai rien trouvé avec ce nom...",
                                                     "Je ne peux que vous proposer des pages similaires.",
                                                     "Je suis désolé mais je n'ai trouvé que ça :"])
                                rdfot = random.choice(
                                    ["Que vouliez-vous exactement ?", "Quelle était votre recherche dans cette liste ?",
                                     "Quel sujet est le bon ?",
                                     "Voulez-vous bien m'indiquer la bonne page à charger ?"])
                                em.set_footer(text=rdfot)
                                msg = await self.bot.send_message(message.channel, msg, embed=em)
                                rep = await self.bot.wait_for_message(channel=message.channel,
                                                                      author=message.author,
                                                                      timeout=10)
                                if rep is None:
                                    await self.bot.delete_message(msg)
                                    return True
                                elif rep.content.lower() in ["rien", "nvm", "nevermind", "stop", "merci",
                                                             "ca sera tout", "ça sera tout", "non merci"]:
                                    poli = random.choice(["Bien entendu.", "D'accord, entendu.", "Très bien."])
                                    await self.bot.send_message(message.channel, poli)
                                    await self.bot.delete_message(msg)
                                    return True
                                elif rep.content.lower() in [l.lower() for l in search]:
                                    search = rep.content
                                    await self.bot.delete_message(msg)
                                elif int(rep.content) in [i[0] for i in liste]:
                                    search = False
                                    for i in liste:
                                        if int(rep.content) == i[0]:
                                            search = i[1]
                                            break
                                    await self.bot.delete_message(msg)
                                    if not search:
                                        await self.bot.send_message(message.channel, "Aucun résulat.")
                                        return
                                else:
                                    await self.bot.delete_message(msg)
                                    return True
                    else:
                        langue = 'en'

    # COMMANDES >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

    @commands.group(name="swiftset", pass_context=True)
    async def _swiftset(self, ctx):
        """Paramètres de Swift"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_swiftset.command(pass_context=True)
    async def ignore(self, ctx):
        """Etre ignoré par Swift - Il ne répondra plus à vos demandes et les services annexes ne seront plus disponibles"""
        membre = self.swf.get_member(ctx.message.author)
        if membre["IGNORE"]:
            membre["IGNORE"] = False
            await self.bot.say("**Swift** ne vous ignore plus. __Lisez attentivement__ le disclaimer suivant...")
            await asyncio.sleep(0.5)
            em = discord.Embed(title="Disclaimer concernant le RGPD", description=self.rgpd, color=0x3162e0)
            em.set_footer(text="─ Ce texte est valable pour tous les services proposés par Turing ─")
            await self.bot.say(embed=em)
        else:
            membre["IGNORE"] = False
            await self.bot.say("**Swift** va désormais vous ignorer. "
                               "*Attention : Un nombre important de fonctionnalités ne sont plus disponibles*")
        self.swf.save()

    @_swiftset.command(name="rgpd")
    async def rgpd_disclamer(self):
        """Affiche le disclaimer RGPD de Turing"""
        em = discord.Embed(title="Disclaimer concernant le RGPD", description=self.rgpd, color=0x3162e0)
        em.set_footer(text="─ Ce texte est valable pour tous les services proposés par Turing ─")
        await self.bot.say(embed=em)

    @_swiftset.group(name="mod", pass_context=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def _swiftset_mod(self, ctx):
        """Paramètres spéciaux réservés à la modération"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_swiftset_mod.command(pass_context=True)
    async def toggle(self, ctx):
        """Active ou désactive l'Assistant personnel Swift sur le serveur"""
        serv = self.get_server(ctx.message.server)
        if serv["ACTIF"]:
            serv["ACTIF"] = False
            await self.bot.say("**Swift** à été désactivé avec succès.")
        else:
            serv["ACTIF"] = True
            await self.bot.say("**Swift** à été activé avec succès. __Lisez attentivement__ le disclaimer suivant...")
            await asyncio.sleep(0.5)
            em = discord.Embed(title="Disclaimer concernant le RGPD", description=self.rgpd, color=0x3162e0)
            em.set_footer(text="─ Ce texte est valable pour tous les services proposés par Turing ─")
            await self.bot.say(embed=em)
        self.sys_save()

    @_swiftset_mod.command(pass_context=True)
    async def repost(self, ctx):
        """Détecte un repost d'URL et le signale"""
        sys = self.get_server(ctx.message.server)["SERVICES"]
        if sys["repost"]:
            sys["repost"] = False
            await self.bot.say("**Service désactivé** ─ Les reposts ne seront désormais plus signalés.")
        else:
            sys["repost"] = True
            await self.bot.say("**Service activé** ─ Les reposts d'URL seront signalés par une réaction ♻ au message.")
        self.sys_save()

    @_swiftset_mod.command(pass_context=True)
    async def afk(self, ctx):
        """Affiche aux membres vous mentionnant que vous êtes AFK (+ raison)"""
        sys = self.get_server(ctx.message.server)["SERVICES"]
        if sys["afk"]:
            sys["afk"] = False
            await self.bot.say("**Service désactivé** ─ Vos absences ne seront plus rappelés aux membres vous mentionnant.")
        else:
            sys["afk"] = True
            await self.bot.say("**Service activé** ─ Ajouter le mot `afk` à votre message vous permettra de signaler votre absence.")
        self.sys_save()

    @_swiftset_mod.command(pass_context=True)
    async def spoil(self, ctx):
        """Permet l'utilisation de la balise spoil afin de cacher vos messages"""
        sys = self.get_server(ctx.message.server)["SERVICES"]
        if sys["spoil"]:
            sys["spoil"] = False
            await self.bot.say("**Service désactivé** ─ La balise spoil n'est plus prise en compte.")
        else:
            sys["spoil"] = True
            await self.bot.say("**Service activé** ─ Commencer votre message par `§` ou `spoil:` vous permettra de cacher votre message.")
        self.sys_save()

    @_swiftset_mod.command(pass_context=True)
    async def quote(self, ctx):
        """Permet l'utilisation de blocs de citations [expérimental]"""
        sys = self.get_server(ctx.message.server)["SERVICES"]
        if sys["quote"]:
            sys["quote"] = False
            await self.bot.say("**Service désactivé** ─ Les blocs de citations ne peuvent plus être créés.")
        else:
            sys["quote"] = True
            await self.bot.say("**Service activé** ─ Créez un bloc de citation en réagissant avec 🗨 ou 💬 sur le message désiré.")
        self.sys_save()

    @_swiftset_mod.command(pass_context=True)
    async def chrono(self, ctx):
        """Créer des messages chronométrés (de 1 à 60s)"""
        sys = self.get_server(ctx.message.server)["SERVICES"]
        if sys["chrono"]:
            sys["chrono"] = False
            await self.bot.say("**Service désactivé** ─ Vous ne pouvez plus créer de messages chronométrés.")
        else:
            sys["chrono"] = True
            await self.bot.say(
                "**Service activé** ─ Créez un message chronométré en ajoutant `.Xs` ou `[Xs]` à votre message, X étant le nombre de secondes (max. 60s).")
        self.sys_save()

    @_swiftset_mod.command(pass_context=True)
    async def annexes(self, ctx):
        """Gestion des services annexes"""
        sys = self.get_server(ctx.message.server, update_services=True)["SERVICES"]
        msg = None
        if sys["annexes"]:
            while True:
                txt = spe = ""
                for a in sys["annexes"]:
                    if a.startswith("ia"):
                        spe += "• `{}` ─ *{}*\n".format(a.upper(), "Activé" if sys["annexes"][a] else "Désactivé")
                    else:
                        txt += "• `{}` ─ *{}*\n".format(a.upper(), "Activé" if sys["annexes"][a] else "Désactivé")
                em = discord.Embed(title="Services annexes disponibles", description=txt, color=0x3162e0)
                em.add_field(name="Greffons d'Assistant", value=spe)
                em.set_footer(text="Saisissez le nom du service pour changer son état ••• ['quit' pour Quitter]")
                if not msg:
                    msg = await self.bot.say(embed=em)
                else:
                    await self.bot.edit_message(msg, embed=em)
                rep = await self.bot.wait_for_message(channel=ctx.message.channel,
                                                      author=ctx.message.author,
                                                      timeout=30)
                if rep is None or rep.content.lower() == "quit":
                    await self.bot.delete_message(msg)
                    return
                elif rep.content.lower() in sys["annexes"]:
                    sys["annexes"][rep.content.lower()] = not sys["annexes"][rep.content.lower()]
                    em.set_footer(text="Service modifié avec succès !")
                    await self.bot.edit_message(msg, embed=em)
                    await asyncio.sleep(2)
                else:
                    em.set_footer(text="Service inconnu.")
                    await self.bot.edit_message(msg, embed=em)
                    await asyncio.sleep(2.25)
        else:
            await self.bot.say("**Aucun service annexe n'est disponible**")


    async def onmessage(self, message):
        author = message.author
        if message.server:

            if not self.swf.get_member(author)["IGNORE"]:
                server, channel, content = message.server, message.channel, message.content
                sys = self.get_server(server)
                opts, cache = sys["SERVICES"], sys["CACHE"]
                session = self.get_context(server)
                if not author.bot:
                    if opts["spoil"]:
                        if content.startswith("§") or content.lower().startswith("spoil:"):
                            await self.bot.delete_message(message)
                            rs = lambda: random.randint(0, 255)
                            color = int('0x%02X%02X%02X' % (rs(), rs(), rs()), 16)
                            balise = "spoil:" if content.lower().startswith("spoil:") else "§"
                            img = False
                            reg = re.compile(r'(https?:\/\/(?:.*)\/\w*\.[A-z]*)', re.DOTALL | re.IGNORECASE).findall(
                                message.content)
                            if reg:
                                img = reg[0]
                            em = discord.Embed(color=color)
                            em.set_author(name=message.author.name, icon_url=message.author.avatar_url)
                            em.set_footer(text="👁 ─ Dévoiler le spoil (en MP)")
                            msg = await self.bot.send_message(channel, embed=em)
                            session["SPOILS"][msg.id] = {"contenu": content.replace(balise, ""),
                                                         "auteur": message.author.name,
                                                         "avatar": message.author.avatar_url,
                                                         "color": color,
                                                         "img": img}
                            await self.bot.add_reaction(msg, "👁")
                            return

                    if opts["afk"]:
                        for afk in session["AFK"]:
                            if author.id == afk[0]:
                                session["AFK"].remove([afk[0], afk[1], afk[2]])
                        if "afk" in content.lower():
                            raison = " ".join([m.strip() for m in content.split() if "afk" not in m.lower()])
                            session["AFK"].append([author.id, author.name, raison])
                        if message.mentions:
                            for m in message.mentions:
                                for afk in session["AFK"]:
                                    if m.id == afk[0]:
                                        if afk[2] != "":
                                            msg = await self.bot.send_message(channel, "**{}** est AFK — *{}*".format(afk[1], afk[2]))
                                        else:
                                            msg = await self.bot.send_message(channel, "**{}** est AFK — "
                                                                                 "Ce membre sera de retour sous peu...".format(afk[1]))
                                        await asyncio.sleep(8)
                                        await self.bot.delete_message(msg)
                                        return

                    if opts["repost"]:
                        if content.startswith("http"):
                            if content in cache["repost"]:
                                if not author.bot:
                                    await self.bot.add_reaction(message, "♻")
                            else:
                                cache["repost"].append(content)
                                fileIO("data/swift/sys.json", "save", self.sys)

                    if opts["msgchrono"]:
                        r = False
                        regex = re.compile(r"\[(\d+)s\]", re.IGNORECASE | re.DOTALL).findall(content)
                        regex2 = re.compile(r"\.(\d+)s", re.IGNORECASE | re.DOTALL).findall(content)
                        if regex:
                            r = regex[0]
                        elif regex2:
                            r = regex2[0]
                        if r:
                            temps = int(r) if int(r) <= 60 else 60
                            if int(r) > 60:
                                await self.bot.add_reaction(message, "⏳")
                            else:
                                await self.bot.add_reaction(message, "⌛")
                            await asyncio.sleep(temps)
                            await self.bot.delete_message(message)

                    if opts["quote"]:
                        if author.id in session["CITATIONS"]:
                            q = session["CITATIONS"][author.id]
                            em = discord.Embed(description=q["contenu"], color=q["color"], timestamp=q["timestamp"])
                            em.set_author(name=q["auteur"], icon_url=q["avatar"], url=q["msg_url"])
                            em.add_field(name="• Message de {}".format(author.name), value=content)
                            em.set_footer(text="Sur #" + q["channel"])
                            if q["img"]:
                                em.set_thumbnail(url=q["img"])
                            await self.bot.delete_message(message)
                            await self.bot.send_message(channel, q["mention"], embed=em)
                            del session["CITATIONS"][author.id]

                    if opts["annexes"].get("noelshack", True):
                        if "noelshack" in content.lower():
                            output = re.compile(r"https*://www.noelshack.com/(\d{4})-(\d{2,3})-(\d{1,3})-(.*)",
                                                re.IGNORECASE | re.DOTALL).findall(content)
                            output2 = re.compile(r"https*://www.noelshack.com/(\d{4})-(\d{2,3})-(.*)",
                                                 re.IGNORECASE | re.DOTALL).findall(content)
                            if output:  # 2018
                                output = output[0]
                                new_url = "🔗 http://image.noelshack.com/fichiers/{}/{}/{}/{}".format(
                                    output[0], output[1], output[2], output[3])
                                await self.bot.send_message(channel, new_url)
                            elif output2:
                                output2 = output2[0]
                                new_url = "🔗 http://image.noelshack.com/fichiers/{}/{}/{}".format(
                                    output2[0], output2[1], output2[2])
                                await self.bot.send_message(channel, new_url)

                    if opts["annexes"].get("mobiletwitter", True):
                        if "twitter.com" in content:
                            for e in content.split():
                                if e.startswith("https://mobile.twitter.com/"):
                                    new = e.replace("mobile.twitter.com", "twitter.com", 1)
                                    await self.bot.send_message(channel, "🔗 " + new)

                    if opts["annexes"].get("mediagif", True):
                        if "https%3a%2f%2fmedia." in content:
                            routput = re.compile(r'rurl=(.*)&ehk', re.IGNORECASE | re.DOTALL).findall(content)
                            if routput:
                                txt = ""
                                for r in routput:
                                    if r:
                                        txt += "🔗 {}\n".format(unquote(r))
                                if txt:
                                    await self.bot.send_message(channel, txt)

                    if opts["annexes"].get("subreddit", True):
                        if "r/" in content:
                            routput = re.compile(r'(?<!\/|\w|[.-:;])r\/(\w*)(?!\/|\w|[.-:;])', re.IGNORECASE | re.DOTALL
                                                 ).findall(content)
                            if routput:
                                txt = ""
                                for r in routput:
                                    if r:
                                        txt += "🔗 https://www.reddit.com/r/{}/\n".format(r)
                                if txt:
                                    await self.bot.send_message(channel, txt)

                    if message.content.lower().startswith("turing") or self.bot.user.id in [u.id for u in message.mentions]:
                        first = True
                        while True:
                            if await self._wikipedia(message):
                                return

                            if first:
                                await self.bot.send_typing(message.channel)
                                await asyncio.sleep(0.75)
                                rmsg = random.choice(["Que puis-je pour vous {user.name} ?", "Oui ?",
                                                      "Vous avez besoin de moi ?",
                                                      "Que puis-je faire pour vous servir {user.name} ?",
                                                      "Avez-vous besoin de quelque chose ?"])
                                resp = await self.bot.send_message(message.channel, rmsg.format(user=message.author))

                                msg = await self.bot.wait_for_message(channel=channel, author=author, timeout=12)
                                if msg is None:
                                    await self.bot.delete_message(resp)
                                    return
                                elif msg.content.lower() in ["non", "non merci", "ça ira", "ca ira", "non rien"]:
                                    await self.bot.send_typing(message.channel)
                                    await asyncio.sleep(0.6)
                                    rmsg = random.choice(["Si vous avez besoin de moi, n'hésitez pas.", "Entendu.",
                                                          "Très bien.", "Je reste à votre *entière* disposition.",
                                                          "Je reste à votre disposition."])
                                    await self.bot.send_message(message.channel, rmsg)
                                    return
                                elif msg.content.lower() in ["jtm", "je t'aime", "je tem", "je taime"]:
                                    emoji = random.choice(["😍","😏","☺","😘","😅"])
                                    await self.bot.add_reaction(msg, emoji)
                                    return
                                else:
                                    message = msg
                                    first = False
                            else:
                                return


    async def onreactionadd(self, reaction, user):
        message = reaction.message
        if not hasattr(message, "server"):
            return
        author = message.author
        if not self.swf.get_member(author)["IGNORE"]:
            server, channel = message.server, message.channel
            content = message.content
            opts, cache = self.get_server(server)["SERVICES"], self.get_server(server)["CACHE"]
            session = self.get_context(server)
            if not user.bot:

                if reaction.emoji == "👁" and opts["spoil"]:
                    if message.id in session["SPOILS"]:
                        await self.bot.remove_reaction(message, "👁", user)
                        p = session["SPOILS"][message.id]
                        em = discord.Embed(color=p["color"], description=p["contenu"])
                        em.set_author(name=p["auteur"], icon_url=p["avatar"])
                        if p["img"]:
                            em.set_image(url=p["img"])
                        try:
                            await self.bot.send_message(user, embed=em)
                        except:
                            print("Impossible d'envoyer le Spoil à {} (Bloqué)".format(user.name))

                if reaction.emoji in ["💬","🗨"] and opts["quote"]:
                    if user.id not in session["CITATIONS"]:
                        contenu = content if content else ""
                        if message.embeds:
                            if "description" in message.embeds[0]:
                                contenu += "\n```{}```".format(message.embeds[0]["description"])
                        msgurl = "https://discordapp.com/channels/{}/{}/{}".format(server.id, message.channel.id, message.id)
                        timestamp = message.timestamp
                        img = False
                        if message.attachments:
                            up = message.attachments[0]["url"]
                            contenu += " [image]({})".format(up)
                            for i in ["png", "jpeg", "jpg", "gif"]:
                                if i in up:
                                    img = up
                        reg = re.compile(r'(https?://(?:.*)/\w*\.[A-z]*)', re.DOTALL | re.IGNORECASE).findall(message.content)
                        if reg:
                            img = reg[0]
                        session["CITATIONS"][user.id] = {"contenu": contenu,
                                                      "color": author.color,
                                                      "auteur": author.name,
                                                      "avatar": author.avatar_url,
                                                      "msg_url": msgurl,
                                                      "img": img,
                                                      "timestamp": timestamp,
                                                      "channel": channel.name,
                                                         "mention": author.mention}
                        await self.bot.remove_reaction(message, reaction.emoji, user)


def check_folders():
    if not os.path.exists("data/swift"):
        print("Creation du fichier swift ...")
        os.makedirs("data/swift")


def check_files():
    if not os.path.isfile("data/swift/data.json"):
        print("Création de swift/data.json ...")
        fileIO("data/swift/data.json", "save", {})

    if not os.path.isfile("data/swift/sys.json"):
        print("Création de swift/sys.json ...")
        fileIO("data/swift/sys.json", "save", {})

def setup(bot):
    check_folders()
    check_files()
    n = Swift(bot)
    bot.add_listener(n.onmessage, "on_message")
    bot.add_listener(n.onreactionadd, "on_reaction_add")
    bot.add_cog(n)
