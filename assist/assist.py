import os
import random
import re
from copy import deepcopy

import aiohttp
import discord
import wikipedia
import wikipediaapi
from __main__ import send_cmd_help
from discord.ext import commands
from sympy import sympify

from .utils import checks
from .utils.dataIO import fileIO, dataIO


class Assist:
    """Assistant intelligent en langage naturel & fonctionnalités à l'écrit"""
    def __init__(self, bot):
        self.bot = bot
        self.sys = dataIO.load_json("data/assist/sys.json")
        self.def_sys = {"ASSIST": True, "ANTI-SPOIL": True, "ASSIST_BALISE": False, "AFK": [], "SPOILS": {}}
        self.mkr = dataIO.load_json("data/assist/mkr.json")
        self.session = aiohttp.ClientSession()

    def __unload(self):
        self.session.close()

# DEFS  --------------------------------

    def redux(self, string: str, separateur: str = ".", limite: int = 2000):
        n = -1
        while len(separateur.join(string.split(separateur)[:n])) >= limite:
            n -= 1
        return separateur.join(string.split(separateur)[:n]) + separateur

    def wiki(self, recherche: str, langue: str = 'fr', souple: bool = True):
        wikipedia.set_lang(langue)
        wikiplus = wikipediaapi.Wikipedia(langue)
        s = wikipedia.search(recherche, 8, True)
        try:
            if s[1]:
                r = s[1]
            else:
                r = s[0][0] if s[0] else None
            if r:
                page = wikipedia.page(r, auto_suggest=souple)
                images = page.images
                image = images[0]
                for i in images:
                    if i.endswith(".png") or i.endswith(".gif") or i.endswith(".jpg") or i.endswith(".jpeg"):
                        image = i
                resum = page.summary
                if not resum:
                    resum = "Contenu indisponible"
                if len(resum) + len(r) > 1995:
                    resum = self.redux(resum, limite=1960)
                p = wikiplus.page(r)
                resum += "\n\n[En savoir plus...]({})".format(p.fullurl)
                em = discord.Embed(title=r.title(), description=resum, color=0xeeeeee)
                em.set_thumbnail(url=image)
                em.set_footer(text="Similaire: {}".format(", ".join(s[0])))
                return em
            else:
                if langue == "en":
                    return "Impossible de trouver {}".format(recherche)
                else:
                    return self.wiki(recherche, "en")
        except:
            if langue == "en":
                if souple:
                    if s[0]:
                        if len(s[0]) >= 2:
                            wikipedia.set_lang("fr")
                            s = wikipedia.search(recherche, 3, True)
                            return "**Introuvable** | Réessayez peut-être avec *{}* ?".format(s[0][1])
                        else:
                            return "**Introuvable** | Aucun résultat pour *{}*".format(recherche)
                    else:
                        return "**Introuvable** | Aucun résultat pour *{}*".format(recherche)
                else:
                    return self.wiki(recherche, "en", False)
            else:
                if souple:
                    return self.wiki(recherche, "en")
                else:
                    return self.wiki(recherche, "fr", False)

# ========== COMMANDES-FONCTIONS ============

    @commands.command(pass_context=True)
    async def calcule(self, ctx, *calcul):
        """Permet de calculer une expression donnée"""
        calcul = " ".join(calcul)
        em = discord.Embed(title=calcul, description="`" + str(sympify(calcul)) + "`", color=ctx.message.author.color)
        await self.bot.say(embed=em)

    @commands.command(pass_context=True)
    async def wikipedia(self, ctx, *recherche):
        """Cherche quelque chose sur Wikipedia (FR ou EN)"""
        recherche = " ".join(recherche)
        r = self.wiki(recherche)
        if type(r) is str:
            await self.bot.say(r)
        else:
            try:
                await self.bot.say(embed=r)
            except:
                await self.bot.say("**Erreur** | La ressource demandée est indisponible")

# PARAMETRES =====================================

    @commands.group(name="assist", pass_context=True, no_pm=True)
    @checks.admin_or_permissions(ban_members=True)
    async def _assist(self, ctx):
        """Paramètres du module Assist"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_assist.command(pass_context=True)
    async def toggle(self, ctx):
        """Active/désactive l'Assistant sur le serveur (ne désactive pas les fonctionnalités annexes)"""
        server = ctx.message.server
        if server.id not in self.sys:
            self.sys[server.id] = self.def_sys
        if self.sys[server.id]["ASSIST"]:
            self.sys[server.id]["ASSIST"] = False
            await self.bot.say("**Succès** | L'assistant à été désactivé sur ce serveur")
        else:
            self.sys[server.id]["ASSIST"] = True
            await self.bot.say("**Succès** | L'assistant à été activé sur ce serveur")
        fileIO("data/assist/sys.json", "save", self.sys)

    @_assist.command(pass_context=True)
    async def balise(self, ctx, balise: str = None):
        """Permet de changer la balise d'invocation (Par défaut la mention du bot)"""
        server = ctx.message.server
        if server.id not in self.sys:
            self.sys[server.id] = self.def_sys
        if balise:
            self.sys[server.id]["ASSIST_BALISE"] = balise
            await self.bot.say("**Changée** | La balise est désormais `{}`".format(balise))
        else:
            self.sys[server.id]["ASSIST_BALISE"] = False
            await self.bot.say("**Retirée** | La balise par défaut est la mention du bot")
        fileIO("data/assist/sys.json", "save", self.sys)

    @_assist.command(pass_context=True)
    async def antispoil(self, ctx):
        """Active/désactive l'anti-spoil §"""
        server = ctx.message.server
        if server.id not in self.sys:
            self.sys[server.id] = self.def_sys
        if self.sys[server.id]["ANTI-SPOIL"]:
            self.sys[server.id]["ANTI-SPOIL"] = False
            await self.bot.say("**Succès** | La balise spoil  été désactivée")
        else:
            self.sys[server.id]["ANTI-SPOIL"] = True
            await self.bot.say("**Succès** | La balise spoil est active (§)")
        fileIO("data/assist/sys.json", "save", self.sys)

    @_assist.command(pass_context=True)
    async def afk(self, ctx):
        """Active/désactive la détection d'AFK"""
        server = ctx.message.server
        if server.id not in self.sys:
            self.sys[server.id] = self.def_sys
        if type(self.sys[server.id]["AFK"]) is list:
            self.sys[server.id]["AFK"] = False
            await self.bot.say("**Succès** | La fonction \"AFK\" est désactivée")
        else:
            self.sys[server.id]["AFK"] = []
            await self.bot.say("**Succès** | La fonction \"AFK\" est activée")
        fileIO("data/assist/sys.json", "save", self.sys)

# DEFS ----------------------------------------

    def _decode(self, message: discord.Message, regex):
        """Décode un regex et le transforme en arguments (str)"""
        server = message.channel.server
        if server.id not in self.sys:
            self.sys[server.id] = self.def_sys
        msg = message.content.lower()
        msg = msg.replace("`", "")
        output = re.compile(regex, re.IGNORECASE | re.DOTALL).findall(msg)
        if output:
            return output
        else:
            return False

    async def execute(self, message: discord.Message, commandstr: str, regex):
        """Transforme un message en commande et l'exécute (pour les commandes simples)"""
        server = message.channel.server
        commandstr = commandstr.replace("{}", "%s")  # Aucazou
        count = commandstr.count("%s")
        args = self._decode(message, regex)
        if args:
            if count == 1:
                args = args[0]
            else:
                while len(args) < count:
                    args.append("")
                if len(args) > count:
                    args = args[:count]
                args = tuple(args[:count])
            command = commandstr % args
            prefix = self.bot.settings.get_prefixes(server)[0]
            new_message = deepcopy(message)
            new_message.content = prefix + command
            await self.bot.process_commands(new_message)
            return True
        else:
            return False

    async def read(self, message):
        """Nouvelle version 'Always Listening'"""
        channel = message.channel
        if not hasattr(channel, 'server'):
            return
        server = channel.server
        author = message.author
        selfcolor = server.get_member(self.bot.user.id).color
        if author.bot:
            return
        content = message.content.lower()
        if "@everyone" in content or "@here" in content:  # Pour les petits malins
            content = content.replace("@everyone", "everyone")
            content = content.replace("@here", "here")
        if server.id not in self.sys:
            self.sys[server.id] = self.def_sys
            fileIO("data/assist/sys.json", "save", self.sys)

        bal = None
        if self.sys[server.id]["ASSIST"]:  # SYSTEME ASSISTANT <<<<<<<<<<<<<<<<<<<<<<<<<
            balise = self.sys[server.id]["ASSIST_BALISE"] if self.sys[
                server.id]["ASSIST_BALISE"] else "<@{}>".format(self.bot.user.id)
            if content.startswith(balise):
                bal = balise
            elif self.bot.user.name.lower() in content.lower().split():
                bal = self.bot.user.name
            if bal:

                content = content.replace(bal, "")
                if content.startswith(" "):
                    content = content[1:]
                once = False
                while True:
                    if await self.execute(message, "ban {}", r"ban <@(.\d+)>"):
                        return  # Ban un membre
                    if await self.execute(message, "kick {}", r"kick <@(.\d+)>"):
                        return  # Kick un membre
                    if await self.execute(message, "calcule {}", r"(?:combien|calcule*) (?:font|fait)?(.*)"):
                        return  # Calcule un truc (Simpy)
                    if await self.execute(message, "wikipedia {}", r"(?:re)?cherche (.*)"):
                        return  # Recherche sur Wikipedia en FR puis en EN si nécessaire
                    if await self.execute(message, "help {}", r"(?:aide|explique|help) (.*)"):
                        return  # Propose une aide sur la commande
                    output = re.compile(
                        r"(?:emprisonnes*|lib[èe]res*|met en prison|jail|isole|sort) <@(.\d+)>(?:\s?\w*?\s)?([0-9]*[jhms])?",
                        re.IGNORECASE | re.DOTALL).findall(message.content)
                    if output:
                        u = output[0]
                        plus = " {}".format(u[1]) if u[1] else ""
                        new_message = deepcopy(message)
                        prefix = self.bot.settings.get_prefixes(server)[0]
                        txt = "p <@{}>{}".format(u[0], plus)
                        new_message.content = prefix + txt
                        await self.bot.process_commands(new_message)
                        return

                    if not once:
                        await self.bot.send_typing(channel)
                        msg = await self.bot.wait_for_message(channel=channel, author=author, timeout=15)
                        if msg is None:
                            return
                        else:
                            message = msg
                            once = True
                    else:
                        return



    """async def read(self, message):
        channel = message.channel
        if not hasattr(channel, 'server'):
            return
        server = channel.server
        selfcolor = server.get_member(self.bot.user.id).color
        author = message.author
        if author.bot:
            return
        content = message.content
        if "@everyone" in content or "@here" in content:  # Pour les petits malins
            content = content.replace("@everyone", "everyone")
            content = content.replace("@here", "here")
        if server.id not in self.sys:
            self.sys[server.id] = self.def_sys
            fileIO("data/assist/sys.json", "save", self.sys)

        output = re.compile(r'(\d+)\s?(?=inchs?|pouces?|")', re.IGNORECASE | re.DOTALL).findall(content)
        if output: # POUCES > CM
            unit = int(output[0])
            conv = round(unit * 2.54, 2)
            uc = "cm"
            if conv > 100:
                uc = "m"
                conv = round(conv / 100, 2)
            txt = "**{}** *pouce·s* = **{}** *{}*".format(unit, conv, uc)
            em = discord.Embed(description=txt, color=selfcolor)
            em.set_author(name="Assistant {} — Conversion".format(self.bot.user.name),
                          icon_url=self.bot.user.avatar_url)
            m = await self.bot.send_message(channel, embed=em)
            await asyncio.sleep(10)
            await self.bot.delete_message(m)

        output = re.compile(r'(\d+)\s?(?=feet|foot|pieds?)', re.IGNORECASE | re.DOTALL).findall(content)
        if output: # PIEDS > conv
            unit = int(output[0])
            conv = round(unit * 30.48, 2)
            uc = "cm"
            if conv > 100:
                uc = "m"
                conv = round(conv / 100, 2)
            txt = "**{}** *pied·s* = **{}** *{}*".format(unit, conv, uc)
            em = discord.Embed(description=txt, color=selfcolor)
            em.set_author(name="Assistant {} — Conversion".format(self.bot.user.name),
                          icon_url=self.bot.user.avatar_url)
            m = await self.bot.send_message(channel, embed=em)
            await asyncio.sleep(10)
            await self.bot.delete_message(m)

        output = re.compile(r'(\d+)\s?(?=yards?)', re.IGNORECASE | re.DOTALL).findall(content)
        if output:  # YARDS > conv
            unit = int(output[0])
            conv = round(unit * 91.44, 2)
            uc = "cm"
            if conv > 100:
                uc = "m"
                conv = round(conv / 100, 2)
            txt = "**{}** *yard·s* = **{}** *{}*".format(unit, conv, uc)
            em = discord.Embed(description=txt, color=selfcolor)
            em.set_author(name="Assistant {} — Conversion".format(self.bot.user.name),
                          icon_url=self.bot.user.avatar_url)
            m = await self.bot.send_message(channel, embed=em)
            await asyncio.sleep(10)
            await self.bot.delete_message(m)

        output = re.compile(r'(\d+)\s?(?=pounds?|livres?)', re.IGNORECASE | re.DOTALL).findall(content)
        if output:  # POUNDS > conv
            unit = int(output[0])
            conv = round(unit * 453.592, 2)
            uc = "g"
            if conv > 1000:
                uc = "kg"
                conv = round(conv / 1000, 2)
            txt = "**{}** *livre·s* = **{}** *{}*".format(unit, conv, uc)
            em = discord.Embed(description=txt, color=selfcolor)
            em.set_author(name="Assistant {} — Conversion".format(self.bot.user.name),
                          icon_url=self.bot.user.avatar_url)
            m = await self.bot.send_message(channel, embed=em)
            await asyncio.sleep(10)
            await self.bot.delete_message(m)

        output = re.compile(r'(\d+)\s?(?=onces?)', re.IGNORECASE | re.DOTALL).findall(content)
        if output:  # POUNDS > conv
            unit = int(output[0])
            conv = round(unit * 28.3495, 2)
            uc = "g"
            if conv > 1000:
                uc = "kg"
                conv = round(conv / 1000, 2)
            txt = "**{}** *once·s* = **{}** *{}*".format(unit, conv, uc)
            em = discord.Embed(description=txt, color=selfcolor)
            em.set_author(name="Assistant {} — Conversion".format(self.bot.user.name),
                          icon_url=self.bot.user.avatar_url)
            m = await self.bot.send_message(channel, embed=em)
            await asyncio.sleep(10)
            await self.bot.delete_message(m)

        if type(self.sys[server.id]["AFK"]) is list:  # SYSTEME AFK <<<<<<<<<<<<<<<<<<<<<<<<
            for afk in self.sys[server.id]["AFK"]:
                if author.id == afk[0]:
                    self.sys[server.id]["AFK"].remove([afk[0], afk[1], afk[2]])
            if "afk" in content.lower():
                if content.lower().startswith("j'afk"):
                    raison = content.lower().replace("j'afk", "", 1)
                else:
                    raison = content.lower().replace("afk", "", 1)
                if raison.startswith(" "):
                    raison = raison[1:]
                self.sys[server.id]["AFK"].append([author.id, author.name, raison])
            if message.mentions:
                for m in message.mentions:
                    for afk in self.sys[server.id]["AFK"]:
                        if m.id == afk[0]:
                            if afk[2] != "":
                                await self.bot.send_message(channel, "**__{}__ est AFK** | *{}*".format(afk[1], afk[2]))
                            else:
                                await self.bot.send_message(channel, "**__{}__ est AFK** | "
                                                                     "Ce membre sera de retour sous peu".format(afk[1]))

        if self.sys[server.id]["ANTI-SPOIL"]: # BALISE SPOIL <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
            if content.startswith("§") or content.lower().startswith("spoil:"):
                rs = lambda: random.randint(0, 255)
                color = int('0x%02X%02X%02X' % (rs(), rs(), rs()), 16)
                balise = "spoil:" if content.lower().startswith("spoil:") else "§"
                await self.bot.delete_message(message)
                em = discord.Embed(color=color)
                em.set_author(name=message.author.name, icon_url=message.author.avatar_url)
                em.set_footer(text="👁 ─ Voir le spoil")
                msg = await self.bot.send_message(channel, embed=em)
                self.sys[server.id]["SPOILS"][msg.id] = {"TEXTE": content.replace(balise, ""),
                                                             "AUTEUR": message.author.name,
                                                             "AUTEURIMG": message.author.avatar_url}
                await self.bot.add_reaction(msg, "👁")
                return

        if self.sys[server.id]["ASSIST"]:  # SYSTEME ASSISTANT <<<<<<<<<<<<<<<<<<<<<<<<<
            balise = self.sys[server.id]["ASSIST_BALISE"] if self.sys[
                server.id]["ASSIST_BALISE"] else "<@{}>".format(self.bot.user.id)
            if content.startswith(balise):
                if await self.execute(message, "ban {}", r"ban <@(.\d+)>"):
                    return  # Ban un membre
                if await self.execute(message, "kick {}", r"kick <@(.\d+)>"):
                    return  # Kick un membre
                if await self.execute(message, "calcule {}", r"(?:combien|calcule*) (?:font|fait)?(.*)"):
                    return  # Calcule un truc (Simpy)
                if await self.execute(message, "wikipedia {}", r"(?:re)?cherche (.*)"):
                    return  # Recherche sur Wikipedia en FR puis en EN si nécessaire
                if await self.execute(message, "help {}", r"(?:aide|explique|help) (.*)"):
                    return  # Propose une aide sur la commande
                output = re.compile(r"(?:emprisonnes*|lib[èe]res*|met en prison|jail|isole|sort) <@(.\d+)>(?:\s?\w*?\s)?([0-9]*[jhms])?", re.IGNORECASE | re.DOTALL).findall(message.content)
                if output:
                    u = output[0]
                    plus = " {}".format(u[1]) if u[1] else ""
                    new_message = deepcopy(message)
                    prefix = self.bot.settings.get_prefixes(server)[0]
                    txt = "p <@{}>{}".format(u[0], plus)
                    new_message.content = prefix + txt
                    await self.bot.process_commands(new_message)
                    return"""


def check_folders():
    if not os.path.exists("data/assist"):
        print("Creation du fichier assist ...")
        os.makedirs("data/assist")


def check_files():
    if not os.path.isfile("data/assist/sys.json"):
        print("Création de assist/sys.json ...")
        fileIO("data/assist/sys.json", "save", {})
    if not os.path.isfile("data/assist/mkr.json"):
        print("Création de assist/mkr.json ...")
        fileIO("data/assist/mkr.json", "save", {})


def setup(bot):
    check_folders()
    check_files()
    n = Assist(bot)
    bot.add_listener(n.read, "on_message")
    bot.add_cog(n)