import os
import random
import re
# from copy import deepcopy

import asyncio
import time
import aiohttp
import discord
# import wikipedia
# import wikipediaapi
from __main__ import send_cmd_help
from discord.ext import commands
# from sympy import sympify

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
        self.context = {"last_save": 0, "servers": {}}
        # self.session = aiohttp.ClientSession()
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

    """def __unload(self):
        self.session.close()"""

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
            for service in ["noelshack", "mobiletwitter", "subreddit"]:
                if service not in self.sys[server.id]["SERVICES"]["annexes"]:
                    self.sys[server.id]["SERVICES"]["annexes"][service] = True
            self.sys_save()
        return self.sys[server.id]

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

    @_swiftset.command(pass_context=True)
    async def rgpd(self, ctx):
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
        txt = ""
        msg = None
        if sys["annexes"]:
            while True:
                for a in sys["annexes"]:
                    txt += "• `{}` ─ *{}*\n".format(a.upper(), "Activé" if sys["annexes"][a] else "Désactivé")
                em = discord.Embed(title="Services annexes disponibles", description=txt, color=0x3162e0)
                em.set_footer(text="Saisissez le nom du service pour changer son état ••• ['quit' pour Quitter]")
                if not msg:
                    msg = await self.bot.say(embed=em)
                else:
                    await self.bot.edit_message(msg, embed=em)
                rep = await self.bot.wait_for_message(channel=ctx.message.channel,
                                                      author=ctx.message.author,
                                                      timeout=30)
                if rep is None or rep.lower() == "quit":
                    await self.bot.delete_message(msg)
                    return
                elif rep.lower() in sys["annexes"]:
                    sys["annexes"][rep.lower()] = not sys["annexes"][rep.lower()]
                    em.set_footer(text="Service modifié avec succès !")
                    await self.bot.edit_message(msg, embed=em)
                    await asyncio.sleep(2)
                else:
                    em.set_footer(text="Service inconnu.")
                    await self.bot.edit_message(msg, embed=em)
                    await asyncio.sleep(2.5)
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
                        if author.id in session["CITATONS"]:
                            q = session["CITATONS"][author.id]
                            em = discord.Embed(description=q["contenu"], color=q["color"], timestamp=q["timestamp"])
                            em.set_author(name=q["auteur"], icon_url=q["avatar"], url=q["msg_url"])
                            em.add_field(name="• Message de {}".format(author.name), value=content)
                            em.set_footer(text="Sur #" + q["channel"])
                            if q["img"]:
                                em.set_thumbnail(url=q["img"])
                            await self.bot.delete_message(message)
                            await self.bot.send_message(channel, embed=em)
                            del session["CITATONS"][author.id]

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

    async def onreactionadd(self, reaction, user):
        message = reaction.message
        if not hasattr(message, "server"):
            return
        author = message.author
        if not self.sfw.get_member(author)["IGNORE"]:
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
                    if user.id not in session["CITATONS"]:
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
                        session["CITATONS"][user.id] = {"contenu": contenu,
                                                      "color": author.color,
                                                      "auteur": author.name,
                                                      "avatar": author.avatar_url,
                                                      "msg_url": msgurl,
                                                      "img": img,
                                                      "timestamp": timestamp,
                                                      "channel": channel.name}
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
