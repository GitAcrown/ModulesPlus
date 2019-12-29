import asyncio
import os
import re
import time
from datetime import datetime

import discord
from __main__ import send_cmd_help
from discord.ext import commands

from .utils import checks
from .utils.dataIO import fileIO, dataIO


class Error(Exception):
    pass


class ServiceUnknown(Error):
    pass


class RepostArchiveCorrupted(Error):
    pass


class ScanAPI:
    """API des outils"""
    def __init__(self, bot, path):
        self.bot = bot
        self.data = dataIO.load_json(path)
        self.last_save = 0
        self.cache = {}

    def save(self, force: bool = False):
        if force:
            fileIO("data/scan/data.json", "save", self.data)
        elif (time.time() - self.last_save) >= 60: # 30s
            fileIO("data/scan/data.json", "save", self.data)
            self.last_save = time.time()

    def get_server(self, server: discord.Server):
        if server.id not in self.data["SERVERS"]:
            self.data["SERVERS"][server.id] = {"repost": {"on": False,
                                                          "delete_delay": 0,
                                                          "cache_days": 14,
                                                          "whitelist": {"users": [],
                                                                        "channels": [],
                                                                        "links": [],
                                                                        "roles": []},
                                                          "cache": {}},
                                               "chrono": {"on": False,
                                                          "max_delay": 30}}
            self.save(True)
        return self.data["SERVERS"][server.id]

    def get_user(self, user: discord.User):
        if user.id not in self.data["USERS"]:
            self.data["USERS"][user.id] = {}
            self.save()
        return self.data["USERS"][user.id]

    def get_service(self, server: discord.Server, service_name: str):
        sys = self.get_server(server)
        if service_name not in sys:
            raise ServiceUnknown("Le service {} n'existe pas pour server.id={}".format(service_name, server.name))
        elif sys[service_name]["on"] is False:
            return False
        else:
            return sys[service_name]

    def clean_repost_cache(self, server: discord.Server):
        sys = self.get_service(server, "repost")
        keep = time.time() - (86400 * sys["cache_days"])
        cache = sys["cache"]
        for url in cache:
            for i in cache[url]:
                if i[3] <= keep:
                    cache[url].remove(i)
            if not cache[url]:
                del cache[url]
        self.save()
        return cache

class Scan:
    """Module d'outils automatisés"""
    def __init__(self, bot):
        self.bot = bot
        self.api = ScanAPI(bot, "data/scan/data.json")

    @commands.group(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def repost(self, ctx):
        """Réglages du détecteur de reposts"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @repost.command()
    async def toggle(self, ctx):
        """Active/Désactive le détecteur de reposts"""
        sys = self.api.get_server(ctx.message.server)["repost"]
        if sys["on"]:
            sys["on"] = False
            await self.bot.say("**Détecteur de repost** ─ Service désactivé")
        else:
            sys["on"] = True
            await self.bot.say("**Détecteur de repost** ─ Service activé")
        self.api.save()

    @repost.command(pass_context=True)
    async def delete(self, ctx, delai: int = 0):
        """Ajoute un délai avant suppression du repost en seconde

        0 = désactivé (défaut)"""
        sys = self.api.get_server(ctx.message.server)["repost"]
        if delai == 0:
            await self.bot.say("**Détecteur de repost** › **Délai de suppression** ─ désactivé")
            sys["delete_delay"] = delai
        elif 1 <= delai <= 300:
            await self.bot.say("**Détecteur de repost** › **Délai de suppression** ─ Réglé sur {}s".format(delai))
            sys["delete_delay"] = delai
        else:
            await self.bot.say("Le délai ne peut pas être supérieur à 300s (5 minutes) ou inférieur à 1s.")
        self.api.save()

    @repost.command(pass_context=True)
    async def archive(self, ctx, jours: int = 14):
        """Modifie le nombre de jours pendant lesquelles un repost est gardé en mémoire

        Par défaut 14 jours, max. 60 jours"""
        sys = self.api.get_server(ctx.message.server)["repost"]
        if 1 <= jours <= 60:
            await self.bot.say("**Détecteur de repost** › **Durée d'archivage** ─ Réglé sur {} jours".format(jours))
            sys["cache_days"] = jours
        else:
            await self.bot.say("Impossible d'archiver plus de **60 jours** de reposts et moins d'un jour.")
        self.api.save()

    @repost.group(pass_context=True, no_pm=True)
    async def whitelist(self, ctx):
        """Gestion de la whitelist repost"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @whitelist.command(pass_context=True)
    async def user(self, ctx, user: discord.Member = None):
        """Ajoute ou retire un membre de la whitelist"""
        sys = self.api.get_server(ctx.message.server)["repost"]["whitelist"]["users"]
        if not user:
            txt = ""
            for i in sys:
                txt += "@{}\n".format(ctx.message.server.get_member(i))
            em = discord.Embed(title="Membres dans la whitelist", description=txt)
            await self.bot.say(embed=em)
            return

        if user.id not in sys:
            sys.append(user.id)
            await self.bot.say("**Détecteur de repost** › **Whitelist** ─ {} est désormais immunisé "
                               "contre le détecteur".format(user.name))
        else:
            sys.remove(user.id)
            await self.bot.say("**Détecteur de repost** › **Whitelist** ─ {} n'est plus immunisé "
                               "contre le détecteur".format(user.name))
        self.api.save()

    @whitelist.command(pass_context=True)
    async def channel(self, ctx, channel: discord.Channel = None):
        """Ajoute ou retire un salon de la whitelist"""
        sys = self.api.get_server(ctx.message.server)["repost"]["whitelist"]["channels"]
        if not channel:
            txt = ""
            for i in sys:
                txt += "#{}\n".format(self.bot.get_channel(i))
            em = discord.Embed(title="Salons dans la whitelist", description=txt)
            await self.bot.say(embed=em)
            return

        if channel.id not in sys:
            sys.append(channel.id)
            await self.bot.say("**Détecteur de repost** › **Whitelist** ─ #{} n'est plus scanné".format(channel.name))
        else:
            sys.remove(channel.id)
            await self.bot.say("**Détecteur de repost** › **Whitelist** ─ #{} est de nouveau scanné".format(channel.name))
        self.api.save()

    @whitelist.command(pass_context=True)
    async def link(self, ctx, url: str = None):
        """Ajoute ou retire une URL de la whitelist"""
        sys = self.api.get_server(ctx.message.server)["repost"]["whitelist"]["links"]
        if not url:
            txt = ""
            for i in sys:
                txt += "`{}`\n".format(i)
            em = discord.Embed(title="Liens dans la whitelist", description=txt)
            await self.bot.say(embed=em)
            return

        if url not in sys:
            sys.append(url)
            await self.bot.say("**Détecteur de repost** › **Whitelist** ─ `{}` sera ignoré".format(url))
        else:
            sys.remove(url)
            await self.bot.say("**Détecteur de repost** › **Whitelist** ─ `{}` n'est plus ignoré".format(url))
        self.api.save()

    @whitelist.command(pass_context=True)
    async def role(self, ctx, role: discord.Role = None):
        """Ajoute ou retire un rôle discord de la whitelist"""
        sys = self.api.get_server(ctx.message.server)["repost"]["whitelist"]["roles"]
        if not role:
            txt = ""
            for i in sys:
                txt += "@{}\n".format(discord.utils.get(ctx.message.server.roles, id=role).name)
            em = discord.Embed(title="Rôles dans la whitelist", description=txt)
            await self.bot.say(embed=em)
            return

        if role.id not in sys:
            sys.append(role.id)
            await self.bot.say("**Détecteur de repost** › **Whitelist** ─ Le rôle {} est désormais immunisé "
                               "contre le détecteur".format(role.name))
        else:
            sys.remove(role.id)
            await self.bot.say("**Détecteur de repost** › **Whitelist** ─ Le rôle {} n'est plus immunisé "
                               "contre le détecteur".format(role.name))
        self.api.save()

    @commands.group(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def chrono(self, ctx):
        """Réglages des messages chronométrés"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @chrono.command()
    async def toggle(self, ctx):
        """Active/Désactive la faculté de chronométrer ses messages"""
        sys = self.api.get_server(ctx.message.server)["chrono"]
        if sys["on"]:
            sys["on"] = False
            await self.bot.say("**Messages chronométrés** ─ Service désactivé")
        else:
            sys["on"] = True
            await self.bot.say("**Messages chronométrés** ─ Service activé")
        self.api.save()

    @chrono.command(pass_context=True)
    async def max(self, ctx, max: int = 30):
        """Modifier le maximum de secondes des messages chronométrés

        Par défaut 30s"""
        sys = self.api.get_server(ctx.message.server)["chrono"]
        if 1 <= max <= 300:
            await self.bot.say("**Messages chronométrés** › **Délai de suppression maximal** ─ Réglé sur {}s".format(max))
            sys["max_delay"] = max
        else:
            await self.bot.say("Le délai maximum ne peut être supérieur à 300s (5 minutes) ou inférieur à 1s.")
        self.api.save()

    async def _scan_repost(self, message: discord.Message):
        """Détecteur de reposts"""
        server = message.server
        service = self.api.get_service(server, "repost")
        if service:
            cache = service["cache"]
            content = message.content

            if message.author.id not in service["whitelist"]["users"]:
                if message.channel.id not in service["whitelist"]["channels"]:
                    if [r.id for r in message.author.roles if r.id not in service["whitelist"]["roles"]]:

                        if "http" in content:
                            scan = re.compile(r'(https?://\S*\.\S*)', re.DOTALL | re.IGNORECASE).findall(content)
                            if scan:
                                url = scan[0]
                                if url not in service["whitelist"]["links"]:
                                    if url in cache:
                                        cache[url].append((message.id, message.channel.id, message.author.id, time.time()))
                                        await self.bot.add_reaction(message, "♻")
                                        self.api.clean_repost_cache(server)  # on conserve les 14 derniers jours
                                        if service["delete_delay"]:
                                            await asyncio.sleep(service["delete_delay"])
                                            try:
                                                await self.bot.delete_message(message)
                                            except:
                                                raise PermissionError("Je n'ai pas les permissions pour supprimer un message")
                                    else:
                                        cache[url] = []
                                        cache[url].append((message.id, message.channel.id, message.author.id, time.time()))
                                        if "youtu.be" in url or "youtube" in url:
                                            dup = self.youtube_duplicata(url)
                                            cache[dup] = []
                                            cache[dup].append(
                                                (message.id, message.channel.id, message.author.id, time.time()))
                                    self.api.save()
        return False

    def youtube_duplicata(self, link):
        """Génère le lien duplicata d'un lien youtube

        Ex. https://www.youtube.com/watch?v=xxxxxxxxx -> https://youtu.be/xxxxxxxx"""
        if "youtu.be" in link:
            vid = link.split("/")[-1]
            return "https://www.youtube.com/watch?v={}".format(vid)
        else:
            vid = link.split("?v=")[-1]
            return "https://youtu.be/{}".format(vid)

    async def _scan_chrono(self, message: discord.Message):
        """Chronomètre un message"""
        server = message.server
        service = self.api.get_service(server, "chrono")
        if service:
            max = service["max_delay"]
            content = message.content
            if "!" in content:
                scan = re.compile(r'!(\d+)s', re.DOTALL | re.IGNORECASE).findall(content)
                if scan:
                    temps = int(scan[1]) if int(scan[1]) <= max else max
                    await self.bot.add_reaction(message, "⌛")
                    await asyncio.sleep(temps)
                    try:
                        await self.bot.delete_message(message)
                    except:
                        await self.bot.send_message(message.channel, "Je n'ai pas pu supprimer le message chronométré.\n"
                                                                     "Soit je n'ai pas les droits, soit on veut me mettre au chômage.")

    async def on_msg(self, message):
        if message.server:
            if self.api.get_service(message.server, "repost"):
                await self._scan_repost(message)
            if self.api.get_service(message.server, "chrono"):
                await self._scan_chrono(message)

    async def on_reaction(self, reaction, user):
        message = reaction.message
        if hasattr(message, "server"):
            if not user.bot:
                server = message.server
                service = self.api.get_service(server, "repost")
                if service:
                    if reaction.emoji == "♻":
                        cache = service["cache"]
                        for url in cache:
                            for log in cache[url]:
                                if message.id == log[0]:
                                    txt = ""
                                    for l in cache[url]:
                                        try:
                                            date = datetime.fromtimestamp(l[3]).strftime("%d/%m/%Y")
                                            if date == datetime.now().strftime("%d/%m/%Y"):
                                                date = "Aujourd'hui à"
                                            heure = " " + datetime.fromtimestamp(l[3]).strftime("%Hh%M")
                                            txt += "• **{}{}** ─ {} sur {}\n".format(date, heure,
                                                                                     server.get_member(l[2]).name,
                                                                                     self.bot.get_channel(l[1]).mention)
                                        except:
                                            raise RepostArchiveCorrupted("Impossible de récupérer un repost de {}".format(url))
                                    if txt:
                                        em = discord.Embed(title="Archive des reposts » {}".format(url),
                                                           description=txt, color=user.color)
                                        em.set_footer(text="Conservés {} jours".format(service["cache_days"]))
                                        try:
                                            await self.bot.send_message(user, embed=em)
                                        except:
                                            notif = await self.bot.send_message(message.channel, "{} » Vous avez demandé l'archive des reposts d'un lien mais vous avez bloqué mes MP, je ne peux pas vous l'envoyer.".format(user.mention))
                                            await asyncio.sleep(10)
                                            await self.bot.delete_message(notif)
                                    return


def check_folders():
    if not os.path.exists("data/scan"):
        print("Creation du fichier Scan ...")
        os.makedirs("data/scan")


def check_files():
    if not os.path.isfile("data/scan/data.json"):
        print("Création de scan/data.json ...")
        fileIO("data/scan/data.json", "save", {"SERVERS": {},
                                               "USERS": {}})


def setup(bot):
    check_folders()
    check_files()
    n = Scan(bot)
    bot.add_listener(n.on_msg, "on_message")
    bot.add_listener(n.on_reaction, "on_reaction_add")
    bot.add_cog(n)