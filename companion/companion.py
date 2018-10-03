import os
import random
import re
# from copy import deepcopy

import asyncio
# import aiohttp
import discord
# import wikipedia
# import wikipediaapi
from __main__ import send_cmd_help
from discord.ext import commands
# from sympy import sympify

from .utils import checks
from .utils.dataIO import fileIO, dataIO

class CompanionAPI:
    """API de l'Assistant personnel Companion"""
    def __init__(self, bot, path):
        self.bot = bot
        self.data = dataIO.load_json(path)
        # self.aiosession = aiohttp.ClientSession()
        self.metasession = {"n_save": 0}

    """def __unload(self):
        self.aiosession.close()"""

    def forcesave(self):
        fileIO("data/companion/data.json", "save", self.data)
        return True

    def save(self, priorite: int = 10):
        if self.metasession["n_save"] >= priorite:
            self.forcesave()
            self.metasession["n_save"] = 0
        else:
            self.metasession["n_save"] += 1

    def get_server(self, server: discord.Server, sub: str = None):
        if server.id not in self.data:
            self.data[server.id] = {"MEMBRES": {},
                                    "OPTIONS": {"repost": True,
                                                "afk": True,
                                                "msgchrono": True,
                                                "spoil": True,
                                                "quote": True,
                                                "autolink": True,
                                                "assistant": True},
                                    "CACHE": {"repost": []}}
        return self.data[server.id][sub] if sub else self.data[server.id]

    def get_member(self, member: discord.Member):
        serv = self.get_server(member.server)["MEMBRES"]
        if member.id not in serv:
            serv[member.id] = {"assistant_ignore": False,
                               "rappels": {},
                               "sysreflet": {}}
            self.forcesave()
        return serv[member.id]

class Companion:
    """Assistant personnel & fonctionnalités automatiques à l'écrit"""
    def __init__(self, bot):
        self.bot = bot
        self.api = CompanionAPI(bot, "data/companion/data.json")
        self.session = {}
        self.disclamer = "Turing analyse et exploite des informations pour vous offrir le meilleur service possible.\n" \
                         "Conformément au *Règlement Général sur la Protection des Données* (RGPD), voici les " \
                         "données qu'il est susceptible d'exploiter et dans quel but :\n\n" \
                         "**1) Analyse constante de vos messages et réactions** dans l'optique de proposer" \
                         " des corrections automatique de liens, des fonctionnalités non proposées par Discord telles " \
                         "que la citation ou la balise spoil ou encore la détection de reposts.\n" \
                         "**2) Extraire de votre utilisation du serveur des données statistiques** afin d'améliorer " \
                         "certains services tels que l'assistant personnel et proposer ces mêmes statistiques à la " \
                         "modération du serveur (logs par exemple).\n" \
                         "**3) Surveiller les changements apportés à votre profil** afin d'en garder un historique " \
                         "utile dans des fonctions de modération et pour vous proposer, notamment, le service de " \
                         "notification personnalisé *Reflet*. Cela comprend votre statut et les programmes lancés que " \
                         "vous laissez apparaître sur votre compte.\n" \
                         "**4) Mettre en mémoire les données que vous fournissez** dans un serveur appartenant à " \
                         "un tiers (<@172376505354158080>). En dehors de quelques rares informations, aucune donnée fournie à " \
                         "Turing n'est cryptée bien que le serveur en question est théoriquement protégé des attaques." \
                         "\n**5) Garder des traces de votre présence même après votre départ du serveur**, qui sont " \
                         "néanmoins inexploitable en votre absence (profils Network par exemple). Il est prévu de " \
                         "pouvoir effacer toute trace de votre présence sur Turing dans un futur proche.\n\n" \
                         "*En utilisant les services proposés par Turing, vous acceptez l'ensemble de ces termes*.\n" \
                         "*Pour toute réclamation ou question, contactez Acrown#4424*."

    def get_session(self, server: discord.Server):
        """Renvoie la session en cours de Companion sur le serveur"""
        if server.id not in self.session:
            self.session[server.id] = {"AFK": [],
                                       "QUOTES": {},
                                       "SPOILS": {}}
        return self.session[server.id]

    @commands.group(pass_context=True)
    async def compset(self, ctx):
        """Paramètres personnels de Companion"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @compset.command(pass_context=True)
    async def ignore(self, ctx):
        """Active ou désactive l'assistant personnel pour vous seulement"""
        server = ctx.message.server
        m = self.api.get_member(ctx.message.author)
        if m.get("assistant_ignore", False):
            m["assistant_ignore"] = False
            await self.bot.say("**Assistant** ─ Activé\nInfo : Lisez attentivement le *disclamer* concernant les "
                               "données exploitées par le bot conformément au RGPD.".format(ctx.prefix))
            await asyncio.sleep(1)
            em = discord.Embed(title="Disclamer concernant le RGPD", description=self.disclamer, color=0x3162e0)
            em.set_footer(text="Ce texte est valable pour tous les services proposés par Turing")
            await self.bot.say(embed=em)
        else:
            m["assistant_ignore"] = True
            await self.bot.say("**Assistant** ─ Turing ne vous assistera plus")
        self.api.forcesave()

    @compset.command(pass_context=True)
    async def rgpd(self):
        """Affiche le disclamer de Turing conformément aux dispositions du Règlement Général sur la Protection des Données"""
        await asyncio.sleep(1)
        em = discord.Embed(title="Disclamer concernant le RGPD", description=self.disclamer, color=0x3162e0)
        em.set_footer(text="Ce texte est valable pour tous les services proposés par Turing")
        await self.bot.say(embed=em)

    @commands.group(aliases=["gset"], pass_context=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def globalset(self, ctx):
        """Paramètres globaux de Companion (appliqués sur tout le serveur)"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @globalset.command(pass_context=True)
    async def assistant(self, ctx):
        """Active ou désactive l'assistant sur le serveur"""
        server = ctx.message.server
        sys = self.api.get_server(server, "OPTIONS")
        if sys.get("assistant", False):
            sys["assistant"] = False
            await self.bot.say("**Assistant** ─ Désactivé sur le serveur")
        else:
            sys["assistant"] = True
            await self.bot.say("**Assistant** ─ Activé\nChaque membre peut séparément le désactiver pour eux-même avec "
                               "`{}compset ignore`".format(ctx.prefix))
        self.api.forcesave()

    @globalset.command(pass_context=True)
    async def autolink(self, ctx):
        """Active ou désactive l'aide automatique pour convertir des liens défectueux etc."""
        server = ctx.message.server
        sys = self.api.get_server(server, "OPTIONS")
        if sys.get("autolink", False):
            sys["autolink"] = False
            await self.bot.say("**Aide automatique** ─ Désactivée")
        else:
            sys["autolink"] = True
            await self.bot.say("**Aide automatique** ─ Activée\nJ'essayerai au mieux de vous aider pour vos liens")
        self.api.forcesave()

    @globalset.command(pass_context=True)
    async def repost(self, ctx):
        """Active ou désactive la notification de vos Reposts"""
        server = ctx.message.server
        sys = self.api.get_server(server, "OPTIONS")
        if sys.get("repost", False):
            sys["repost"] = False
            await self.bot.say("**Notificateur de Reposts** ─ Désactivé")
        else:
            sys["repost"] = True
            await self.bot.say("**Notificateur de Reposts** ─ Activé\nUn emoji ♻ viendra vous informer que votre "
                               "message est un repost")
        self.api.forcesave()

    @globalset.command(pass_context=True)
    async def afk(self, ctx):
        """Active ou désactive la notification des AFK"""
        server = ctx.message.server
        sys = self.api.get_server(server, "OPTIONS")
        if sys.get("afk", False):
            sys["afk"] = False
            await self.bot.say("**Notificateur d'AFK** ─ Désactivé")
        else:
            sys["afk"] = True
            await self.bot.say("**Notificateur d'AFK** ─ Activé\nMettez `afk` dans votre message pour indiquer "
                               "votre absence")
        self.api.forcesave()

    @globalset.command(pass_context=True)
    async def spoil(self, ctx):
        """Active ou désactive la balise Spoil"""
        server = ctx.message.server
        sys = self.api.get_server(server, "OPTIONS")
        if sys.get("spoil", False):
            sys["spoil"] = False
            await self.bot.say("**Balise Spoil** ─ Désactivé")
        else:
            sys["spoil"] = True
            await self.bot.say("**Balise Spoil** ─ Activé\nMettez `§` au début de votre message pour le cacher")
        self.api.forcesave()

    @globalset.command(pass_context=True)
    async def quote(self, ctx):
        """Active ou désactive la possibilité de faire des citations"""
        server = ctx.message.server
        sys = self.api.get_server(server, "OPTIONS")
        if sys.get("quote", False):
            sys["quote"] = False
            await self.bot.say("**Bloc de citation** ─ Désactivé")
        else:
            sys["quote"] = True
            await self.bot.say("**Bloc de citation** ─ Activé\nAjoutez l'emoji 🗨 ou 💬 à un message pour le citer")
        self.api.forcesave()

    @globalset.command(pass_context=True)
    async def msgchrono(self, ctx):
        """Active ou désactive la possibilité de créer des messages chronométrés"""
        server = ctx.message.server
        sys = self.api.get_server(server, "OPTIONS")
        if sys.get("msgchrono", False):
            sys["msgchrono"] = False
            await self.bot.say("**Messages chronométrés** ─ Désactivés")
        else:
            sys["msgchrono"] = True
            await self.bot.say("**Messages chronométrés** ─ Activés\nMettez `.Xs` dans votre message avec X la valeur "
                               "en secondes au bout desquelles votre message sera supprimé (max. 60).")
        self.api.forcesave()

    async def on_message_post(self, message):
        author = message.author
        if message.server:
            if not self.api.get_member(author)["assistant_ignore"]:
                server, channel = message.server, message.channel
                content = message.content
                try:
                    opts, cache = self.api.get_server(server, "OPTIONS"), self.api.get_server(server, "CACHE")
                    session = self.get_session(server)
                except:
                    return
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
                            em.set_footer(text="👁 ─ Dévoiler le spoil (MP)")
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
                                self.api.save()

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
                            await self.bot.add_reaction(message, "⏱")
                            await asyncio.sleep(temps)
                            await self.bot.delete_message(message)

                    if opts["quote"]:
                        if author.id in session["QUOTES"]:
                            q = session["QUOTES"][author.id]
                            em = discord.Embed(description=q["contenu"], color=q["color"], timestamp=q["timestamp"])
                            em.set_author(name=q["auteur"], icon_url=q["avatar"], url=q["msg_url"])
                            em.add_field(name="• Réponse de {}".format(author.name), value=content)
                            em.set_footer(text="Sur #" + q["channel"])
                            if q["img"]:
                                em.set_thumbnail(url=q["img"])
                            await self.bot.delete_message(message)
                            await self.bot.send_message(channel, embed=em)
                            del session["QUOTES"][author.id]

                    if opts["autolink"]:
                        if "noelshack" in content.lower():
                            output = re.compile(r"https*://www.noelshack.com/(\d{4})-(\d{2,3})-(\d{1,3})-(.*)",
                                                re.IGNORECASE | re.DOTALL).findall(content)
                            output2 = re.compile(r"https*://www.noelshack.com/(\d{4})-(\d{2,3})-(.*)",
                                                 re.IGNORECASE | re.DOTALL).findall(content)
                            if output:  # 2018
                                output = output[0]
                                new_url = "http://image.noelshack.com/fichiers/{}/{}/{}/{}".format(
                                    output[0], output[1], output[2], output[3])
                                await self.bot.send_message(channel, new_url)
                            elif output2:
                                output2 = output2[0]
                                new_url = "http://image.noelshack.com/fichiers/{}/{}/{}".format(
                                    output2[0], output2[1], output2[2])
                                await self.bot.send_message(channel, new_url)

                        if "twitter.com" in content:
                            for e in content.split():
                                if e.startswith("https://mobile.twitter.com/"):
                                    new = e.replace("mobile.twitter.com", "twitter.com", 1)
                                    await self.bot.send_message(channel, new)

                        if "r/" in content:
                            routput = re.compile(r'(?<!\/|\w|[.-:;])r\/(\w*)(?!\/|\w|[.-:;])', re.IGNORECASE | re.DOTALL
                                                 ).findall(content)
                            if routput:
                                txt = ""
                                for r in routput:
                                    if r:
                                        txt += "• https://www.reddit.com/r/{}/\n".format(r)
                                if txt:
                                    await self.bot.send_message(channel, txt)

    async def get_on_reaction_add(self, reaction, user):
        message = reaction.message
        if not hasattr(message, "server"):
            return
        author = message.author
        if not self.api.get_member(author)["assistant_ignore"]:
            server, channel = message.server, message.channel
            content = message.content
            opts, cache = self.api.get_server(server, "OPTIONS"), self.api.get_server(server, "CACHE")
            session = self.get_session(server)
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
                    if user.id not in session["QUOTES"]:
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
                        session["QUOTES"][user.id] = {"contenu": contenu,
                                                      "color": author.color,
                                                      "auteur": author.name,
                                                      "avatar": author.avatar_url,
                                                      "msg_url": msgurl,
                                                      "img": img,
                                                      "timestamp": timestamp,
                                                      "channel": channel.name}
                        await self.bot.remove_reaction(message, reaction.emoji, user)


def check_folders():
    if not os.path.exists("data/companion"):
        print("Creation du fichier companion ...")
        os.makedirs("data/companion")


def check_files():
    if not os.path.isfile("data/companion/data.json"):
        print("Création de companion/data.json ...")
        fileIO("data/companion/data.json", "save", {})

def setup(bot):
    check_folders()
    check_files()
    n = Companion(bot)
    bot.add_listener(n.on_message_post, "on_message")
    bot.add_listener(n.get_on_reaction_add, "on_reaction_add")
    bot.add_cog(n)
