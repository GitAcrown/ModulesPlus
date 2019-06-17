import asyncio
import os
import random
import re
import time
from datetime import datetime

import discord
import praw
from discord.ext import commands

from .utils import checks
from .utils.dataIO import fileIO, dataIO


class CentralAPI:
    """API de Central - Assistant personnel"""
    def __init__(self, bot, path):
        self.bot = bot
        self.data = dataIO.load_json(path)
        self.meta = {"last_save": 0}

    def save(self, force: bool = False):
        if force:
            fileIO("data/central/data.json", "save", self.data)
        elif (time.time() - self.meta["last_save"]) >= 30: # 30s
            fileIO("data/central/data.json", "save", self.data)
            self.meta["last_save"] = time.time()

    def get_member(self, user: discord.Member):
        """Renvoie le profil Central du membre"""
        if user.id not in self.data:
            self.data[user.id] = {}
            self.save()
        return self.data[user.id]

class Central:
    """Assistant personnel embarqué - Pour vous servir"""
    def __init__(self, bot):
        self.bot = bot
        self.ctr = CentralAPI(bot, "data/central/data.json")
        self.sys = dataIO.load_json("data/central/sys.json")
        self.metasys = {"ls": 0}
        self.context = {}
        self.reddit = praw.Reddit(client_id='uE7NMd2ISBWR7w',
                     client_secret='2pZk2tj9oHMMz_BJCzbJd4JrIRY',
                     user_agent='discordbot:Stay.:1.0 (by /u/Nordsko)')

    def save_sys(self, force: bool = False):
        if force:
            fileIO("data/central/sys.json", "save", self.sys)
        elif (time.time() - self.metasys["ls"]) >= 30: # 30s
            fileIO("data/central/sys.json", "save", self.sys)
            self.metasys["ls"] = time.time()

    def reset_sys(self):
        self.sys = {}
        self.save_sys(True)
        return True

    def get_sys(self, server: discord.Server):
        """Renvoie les paramètres du serveur"""
        if server.id not in self.sys:
            self.sys[server.id] = {"SERVICES": {},
                                   "CACHE": {}}
            self.save_sys(True)
        return self.sys[server.id]

    def check_service(self, server: discord.Server, nom: str):
        """Vérifie si un service existe, s'il est activé et renvoie éventuellement le cache lié"""
        sys, cache = self.get_sys(server)["SERVICES"], self.get_sys(server)["CACHE"]
        service = self.get_service(nom)
        if service:
            if nom not in sys:
                self.get_sys(server)["SERVICES"][nom] = True
                if service[1] != False:
                    self.get_sys(server)["CACHE"][nom] = service[1]
                self.save_sys()
            return sys[nom]
        return ()

    def get_service(self, nom: str = None):
        """Renvoie les infos sur un service"""
        serv_list = [("repost", {}, "Détecte les reposts de liens web"),
                     ("msg_chrono", False, "Permet de créer des messages chronométrés avec !Xs"),
                     ("reddit", False, "Détecte les subreddit et affiche des informations à propos de celui-ci"),
                     ("bave", False, "???")]
        if nom:
            for s in serv_list:
                if s[0] == nom.lower():
                    return s
            return ()
        return serv_list

    async def _reddit_embed(self, message: discord.Message):
        server = message.server
        if self.check_service(server, "reddit"):
            content = message.content
            if "r/" in content:
                op = re.compile(r'(?<!\/|\w|[.-:;])r\/(\w*)(?!\/|\w|[.-:;])', re.IGNORECASE | re.DOTALL).findall(
                    content)
                if op:
                    for r in op:
                        try:
                            reddit = self.reddit.subreddits.search_by_name(r, exact=True)[0]
                            if reddit.over18:
                                txt = ""
                                color = int('0x{}'.format(reddit.key_color[1:]), 16) if reddit.key_color else 0xfd4300
                                for submit in reddit.hot(limit=3):
                                    txt += "· ||**[{0}](https://www.reddit.com{1})**|| (u/[{2}](https://www.reddit.com/user/{2}))\n".format(
                                        submit.title, submit.permalink, submit.author.name if submit.author else "???")
                                em = discord.Embed(url="https://www.reddit.com/r/{}/".format(r),
                                                   title="r/" + reddit.display_name.title() + " ─ Hot",
                                                   description=txt, color=color)
                                em.set_footer(text="Classé NSFW ─ Les titres sont cachés")
                                notif = await self.bot.send_message(message.channel, embed=em)
                                await asyncio.sleep(30)
                                await self.bot.delete_message(notif)
                            else:
                                txt = ""
                                color = int('0x{}'.format(reddit.key_color[1:]), 16) if reddit.key_color else 0xfd4300
                                for submit in reddit.hot(limit=3):
                                    txt += "· **[{0}](https://www.reddit.com{1})** (u/[{2}](https://www.reddit.com/user/{2}))\n".format(
                                        submit.title, submit.permalink, submit.author.name if submit.author else "???")
                                em = discord.Embed(url="https://www.reddit.com/r/{}/".format(r),
                                                   title="r/" + reddit.display_name.title() + " ─ Hot",
                                                   description=txt, color=color)
                                if reddit.banner_img:
                                    em.set_image(url=reddit.banner_img)
                                notif = await self.bot.send_message(message.channel, embed=em)
                                await asyncio.sleep(30)
                                await self.bot.delete_message(notif)
                        except Exception as e:
                            print(e)
                            pass
        return False

    def clean_repost_cache(self, stock):
        keep = time.time() - 604800
        for url in stock:
            for i in stock[url]:
                if i[3] < keep:
                    stock[url].remove(i)
            if url == []:
                del stock[url]
        return stock

    async def _repost_detect(self, message: discord.Message):
        server = message.server
        if self.check_service(server, "repost"):
            cache = self.get_sys(server)["CACHE"]
            content = message.content
            if "http" in content:
                op = re.compile(r'(https?:+\/\/[^:\/\s]+(?:[^?]|\?v)*)', re.DOTALL | re.IGNORECASE).findall(content)
                if op:
                    url = op[0]
                    if url in cache["repost"]:
                        cache["repost"][url].append((message.id, message.channel.id, message.author.id, time.time()))
                        if len(cache["repost"]) >= 100:
                            cache["repost"] = self.clean_repost_cache(cache["repost"])
                        await self.bot.add_reaction(message, "♻")
                    else:
                        cache["repost"][url] = []
                        cache["repost"][url].append((message.id, message.channel.id, message.author.id, time.time()))
                    self.save_sys()
        return False

    async def on_msg(self, message):
        if message.server:
            server = message.server
            if self.check_service(server, "repost"):
                await self._repost_detect(message)
            if self.check_service(server, "reddit"):
                await self._reddit_embed(message)
            if self.check_service(server, "msg_chrono"):
                op = re.compile(r"!(\d+)s", re.IGNORECASE | re.DOTALL).findall(message.content)
                if op:
                    temps = int(op[0]) if int(op[0]) <= 30 else 30
                    await self.bot.add_reaction(message, "⌛")
                    await asyncio.sleep(temps)
                    try:
                        await self.bot.delete_message(message)
                    except:
                        rdm = random.choice(["Oh, vous avez été plus rapide que moi pour le supprimer...",
                                             "Eh, c'était à moi de supprimer le message, vous voulez pas faire mon boulot à ma place aussi ?!?",
                                             "Qui a supprimé le message chrono ? Qu'il se dénonce !",
                                             "Vous voulez me mettre au chômage à force de supprimer les messages à ma place ?"])
                        await self.bot.send_message(message.channel, rdm)
            if self.check_service(server, "bave"):
                r = random.randint(0, 300)
                if r == 0 or "bave" in message.content.split():
                    await self.bot.add_reaction(message, "💧")

    async def on_reaction(self, reaction, user):
        message = reaction.message
        if hasattr(message, "server"):
            if not user.bot:
                server = message.server
                if self.check_service(server, "repost"):
                    if reaction.emoji == "♻":
                        r_cache = self.get_sys(server)["CACHE"]["repost"]
                        for i in r_cache:
                            for log in r_cache[i]:
                                if message.id == log[0]:
                                    txt = ""
                                    for u in r_cache[i]:
                                        try:
                                            txt += "**{}** ─ par {} sur {}\n".format(datetime.fromtimestamp(
                                                u[3]).strftime("%d/%m/%Y %H:%M"),
                                                                                     server.get_member(u[2]).name,
                                                                                    self.bot.get_channel(u[1]).mention)
                                        except:
                                            print("Impossible de récuperer un ancien repost")
                                            pass
                                    if txt:
                                        em = discord.Embed(title="Repost ─ {}".format(i), description=txt, color=user.color)
                                        try:
                                            await self.bot.send_message(user, embed=em)
                                        except:
                                            notif = await self.bot.send_message(message.channel, "{} ─ Vous avez bloqué mes MP, vous ne pouvez pas voir les reposts.".format(user.mention))
                                            await asyncio.sleep(5)
                                            await self.bot.delete_message(notif)
                                    return

    @commands.command(pass_context=True)
    async def testimg(self, ctx):
        em = discord.Embed(title="Testimg")
        em.set_image(url="https://i.imgur.com/Gc5zR4z.gif")
        await self.bot.say(embed=em)

    @commands.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def services(self, ctx):
        """Gestion des services du Central"""
        server = ctx.message.server
        services = self.get_service()
        msg = None
        while True:
            txt = ""
            for s in services:
                if self.check_service(server, s[0]):
                    txt += "• `{}` ─ **ON**\n".format(s[0])
                else:
                    txt += "• `{}` ─ OFF\n".format(s[0])
            em = discord.Embed(title="Services du Central", description=txt, color=0xfff952)
            em.set_footer(text="Saisissez le nom du service pour le modifier ··· 'Quit' pour quitter")
            if not msg:
                msg = await self.bot.say(embed=em)
            else:
                await self.bot.edit_message(msg, embed=em)

            rep = await self.bot.wait_for_message(channel=ctx.message.channel,
                                                  author=ctx.message.author,
                                                  timeout=30)
            if rep is None or rep.content.lower() in ["quit", "stop", "quitter"]:
                await self.bot.delete_message(msg)
                return
            elif rep.content.lower() in [i[0] for i in services]:
                srv = self.get_service(rep.content.lower())
                self.get_sys(server)["SERVICES"][srv[0]] = not self.get_sys(server)["SERVICES"][srv[0]]
                self.save_sys(True)
                em = discord.Embed(title="Services du Central", description=srv[2], color=0xfff952)
                em.set_footer(text="Service modifié avec succès ─ Patientez S.V.P.")
                await self.bot.edit_message(msg, embed=em)
                await asyncio.sleep(3.5)
            else:
                em.set_footer(text="Service inconnu ─ Réessayez")
                await self.bot.edit_message(msg, embed=em)
                await asyncio.sleep(2)

    @commands.command(pass_context=True, hidden=True)
    async def resetservices(self, ctx):
        self.reset_sys()
        await self.bot.say("**Succès**")


def check_folders():
    if not os.path.exists("data/central"):
        print("Creation du fichier central ...")
        os.makedirs("data/central")


def check_files():
    if not os.path.isfile("data/central/data.json"):
        print("Création de central/data.json ...")
        fileIO("data/central/data.json", "save", {})

    if not os.path.isfile("data/central/sys.json"):
        print("Création de central/sys.json ...")
        fileIO("data/central/sys.json", "save", {})


def setup(bot):
    check_folders()
    check_files()
    n = Central(bot)
    bot.add_listener(n.on_msg, "on_message")
    bot.add_listener(n.on_reaction, "on_reaction_add")
    bot.add_cog(n)
