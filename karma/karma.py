import asyncio
import operator
import os
import random
import re
import time
from copy import deepcopy
from datetime import datetime

import discord
from __main__ import send_cmd_help
from cogs.utils.dataIO import fileIO, dataIO
from discord.ext import commands

from .utils import checks


# TODO:
# - Ajouter des logs de modération (avec catégories etc.) ~ 75%
# - Ajouter fonction de Censure (sim. à la balise spoil)
# - Ajouter les casiers (historiques, karma etc.)
# - Donner un moyen de rendre des rôles persistants
# - Faire vérifier les nouveaux salons par le bot pour ajuster le rôle Prison en fonction
# - Redonner le rôle Prisonnier aux arrivants qui étaient encore en prison au moment de leur départ
# - Donner le moyen d'attribuer des rôles à l'arrivée des membres

class KarmaAPI:
    """API de Karma - Module de modération"""
    def __init__(self, bot, path):
        self.bot = bot
        self.data = dataIO.load_json(path)
        self.context = {"last_save": 0}
        self.update()

    def update(self): # V0.02
        for server in self.data:
            if not "slow" in self.data[server]["META"]:
                self.data[server]["META"]["slow"] = {}
        return True

    def save(self, force: bool = False):
        if force:
            fileIO("data/karma/data.json", "save", self.data)
        elif (time.time() - self.context["last_save"]) >= 180:  # 3 minutes
            fileIO("data/karma/data.json", "save", self.data)
            self.context["last_save"] = time.time()

    def get_server(self, server: discord.Server, sub: str = None):
        if server.id not in self.data:
            opts = {"persist_roles": [],
                    "rules": {},
                    "auto_roles": [],
                    "cache_repost": {},
                    "logs_channels": {},
                    "prison_role": "Prison",
                    "prison_channel": None,
                    "prison_notif": None}
            self.data[server.id] = {"META": opts,
                                    "USERS": {}}
            self.save(True)
        return self.data[server.id][sub] if sub else self.data[server.id]

    def get_user(self, user: discord.Member, sub: str = None):
        server = self.get_server(user.server, "USERS")
        if user.id not in server:
            server[user.id] = {"LOGS": []}
            self.save()
        return server[user.id][sub] if sub else server[user.id]

    async def add_server_logs(self, server: discord.Server, category: str, embed: discord.Embed):
        """Ajouter un log d'une certaine catégorie au serveur donné (si actif)"""
        serv = self.get_server(server, "META")
        if category in serv["logs_channels"]:
            channel = self.bot.get_channel(serv["logs_channels"][category])
            await self.bot.send_message(channel, embed=embed)
            return True
        return False

    def logs_on(self, server: discord.Server, category: str):
        if category in self.get_server(server, "META")["logs_channels"]:
            return True
        return False

class Karma:
    """Ajoute des fonctionnalités de modération et quelques trucs utiles"""
    def __init__(self, bot):
        self.bot = bot
        self.karma = KarmaAPI(bot, "data/karma/data.json")
        self.cache = dataIO.load_json("data/karma/cache.json") # Pour garder des trucs secondaires en mémoire
        self.update_cache()
        self.meta = {"last_save": 0}

    def save_cache(self, force: bool = False):
        if force:
            fileIO("data/karma/cache.json", "save", self.cache)
        elif (time.time() - self.meta["last_save"]) >= 120:  # 2 minutes
            fileIO("data/karma/cache.json", "save", self.cache)
            self.meta["last_save"] = time.time()
        return True

    def get_meta(self, server: discord.Server):
        if server.id not in self.meta:
            self.meta[server.id] = {"spoils": {}}
        return self.meta[server.id]
    
    def update_cache(self):
        for server in self.cache:
            if "SLOW" not in self.cache[server]:
                self.cache[server]["SLOW"] = {}
        self.save_cache(True)

    def get_cache(self, server: discord.Server, sub: str = None):
        if server.id not in self.cache:
            self.cache[server.id] = {"PRISON": {},
                                     "SLOW": {}}
            self.save_cache(True)
        return self.cache[server.id][sub] if sub else self.cache[server.id]

    def check(self, reaction, user):
        return not user.bot

    def supersort(self, l):
        convert = lambda text: float(text) if text.isdigit() else text
        alphanum = lambda key: [convert(c) for c in re.split('([-+]?[0-9]*\.?[0-9]+)', key)]
        l.sort(key=alphanum)
        return l

    def convert_sec(self, form: str, val: int):
        if form == "j":
            return val * 86400
        elif form == "h":
            return val * 3600
        elif form == "m":
            return val * 60
        else:
            return val

    @commands.command(pass_context=True, hidden=True)
    async def lagtest(self, ctx):
        """Rapide calcul du temps de latence de communication entre un membre et le bot"""
        n = 1
        ping = ctx.message.timestamp
        results = []
        while n <= 3:
            msg = await self.bot.say("Pong #{}".format(n))
            pong = msg.timestamp
            diff = (pong - ping).seconds, (pong - ping).microseconds
            results.append(diff)
            ping = pong
            n += 1
        txt = "\n".join(["• {},{}s".format(a, b) for a, b in [i for i in results]])
        await self.bot.say("**Résultats :**\n" + txt)

    @commands.command(aliases=["s"], pass_context=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def slow(self, ctx, user: discord.Member, cooldown: str = "10s", *raison):
        """Passe un membre en mode Slow, imposant un délai entre deux messages

        <cooldown> = Valeur suivie de l'unité (s, m, h, j)"""
        server = ctx.message.server
        data = self.karma.get_server(server, "META")["slow"]
        form, val = cooldown[-1:], int(cooldown[:-1])
        law = self.karma.get_server(ctx.message.server, "META")["rules"]
        art = False
        if raison:
            if raison[0] in law:
                art = raison[0]
                raison = " ".join(raison[1:])
                raison += "\n\n─ **Art. {}**\n```{}```".format(art, law[art])
            else:
                raison = " ".join(raison)
        if not raison and art:
            raison = "Non-respect d'une règle"
        if not raison and not art:
            raison = False

        if user.id not in data:
            data[user.id] = self.convert_sec(form, val)
            self.karma.save(True)
            em = discord.Embed(description="🐢 **Slow** ─ {} ne peut désormais poster qu'un message toutes les {}{}"
                                           "".format(user.mention, val, form), color=0xce4b1f)
            msg = await self.bot.say(embed=em)
            try:
                em = discord.Embed(description="🐢 **Slow** par {} ─ Vous ne pouvez désormais poster qu'un message"
                                               " toutes les {}{}".format(ctx.message.author, val, form))
                if raison:
                    em.add_field(name="Raison", value=raison)
                await self.bot.send_message(user, embed=em)
            except:
                print("SLOW - {} m'a bloqué, impossible de lui envoyer une notification.".format(str(user)))

            if self.karma.logs_on(server, "msg_slow"):
                em = discord.Embed(description="{} est limité par un délai de **{}{}** entre ses messages par {}".format(
                    user.mention, val, form, ctx.message.author.mention), color=0xce4b1f, timestamp=ctx.message.timestamp)
                if raison:
                    em.add_field(name="Raison", value=raison)
                em.set_author(name=str(user) + " ─ Entrée en mode slow", icon_url=user.avatar_url)
                em.set_footer(text="ID:{}".format(user.id))
                await self.karma.add_server_logs(server, "msg_slow", em)

            await asyncio.sleep(8)
            await self.bot.delete_message(msg)
        else:
            if user.id in self.get_cache(server, "SLOW"):
                del self.get_cache(server, "SLOW")[user.id]
                self.save_cache(True)
            del self.karma.get_server(server, "META")["slow"][user.id]
            self.karma.save(True)
            em = discord.Embed(description="🐢 **Slow** ─ {} n'est plus limité·e".format(user.mention), color=0xce4b1f)
            msg = await self.bot.say(embed=em)
            try:
                em = discord.Embed(description="🐢 **Slow** ─ Vous n'êtes plus limité·e")
                await self.bot.send_message(user, embed=em)
            except:
                print("SLOW - {} m'a bloqué, impossible de lui envoyer une notification.".format(str(user)))

            if self.karma.logs_on(server, "msg_slow"):
                em = discord.Embed(description="{} a été libéré du mode Slow par {}".format(
                    user.mention, ctx.message.author.mention), color=0xce4b1f, timestamp=ctx.message.timestamp)
                em.set_author(name=str(user) + " ─ Sortie du mode slow", icon_url=user.avatar_url)
                em.set_footer(text="ID:{}".format(user.id))
                await self.karma.add_server_logs(server, "msg_slow", em)

            await asyncio.sleep(8)
            await self.bot.delete_message(msg)

    @commands.command(pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def autoroles(self, ctx, *roles):
        """Attribue automatiquement, au hasard, l'un des rôles donnés

        Pour les rôles avec un nom composé, n'oubliez pas les guillemets"""
        if roles:
            if roles[0].lower() in ["reset", "stop", "off"]:
                self.karma.get_server(ctx.message.server, "META")["auto_roles"] = []
                self.karma.save(True)
                await self.bot.say("⚙ **Attribution automatique de rôles** ─ Désactivée")
                return
            liste = []
            txt = ""
            for r in roles:
                if r in [r.name for r in ctx.message.server.roles]:
                    liste.append(r)
                    role = discord.utils.get(ctx.message.server.roles, name=r)
                    txt += "• {}\n".format(role.mention)
            self.karma.get_server(ctx.message.server, "META")["auto_roles"] = liste
            self.karma.save(True)
            em = discord.Embed(title="Attribution auto. des rôles ─ Activé", description=txt)
            em.set_footer(text="Ne changez pas le nom des rôles fournis sous peine d'entraver son fonctionnement")
            await self.bot.say(embed=em)
        elif self.karma.get_server(ctx.message.server, "META")["auto_roles"]:
            txt = ""
            for r in self.karma.get_server(ctx.message.server, "META")["auto_roles"]:
                role = discord.utils.get(ctx.message.server.roles, name=r)
                txt += "• {}\n".format(role.mention)
            em = discord.Embed(title="Attribution auto. des rôles ─ Liste", description=txt)
            em.set_footer(text="Tapez '.autoroles stop' pour désactiver cette fonctionnalité")
            await self.bot.say(embed=em)
        else:
            await self.bot.say("🚩 **Erreur** ─ Tapez la liste des __noms exacts__ des rôles entre guillemets pour activer cette fonction")


    @commands.command(aliases=["p"], pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def prison(self, ctx, user: discord.Member, temps: str = "10m", *raison: str):
        """Emprisonne un membre pour un certain temps (def. 10m)

        <user> = Membre à emprisonner
        <temps> = Valeur suivie de l'unité (m/h/j) ou heure de sortie
        --> Il est possible de moduler la peine en ajoutant + et - devant la durée
        [raison] = Optionnel, rajoute une raison à la peine"""
        ts = datetime.utcnow()
        law = self.karma.get_server(ctx.message.server, "META")["rules"]
        art = False
        if raison:
            if raison[0] in law:
                art = raison[0]
                raison = " ".join(raison[1:])
                raison += "\n\n─ **Art. {}**\n```{}```".format(art, law[art])
            else:
                raison = " ".join(raison)
        if not raison and art:
            raison = "Non-respect d'une règle"
        if not raison and not art:
            raison = False

        message = ctx.message
        server = message.server
        if user.id == self.bot.user.id:
            rand = random.choice(["Il est hors de question que je me mette moi-même en prison ! 😭",
                                  "Non, vous ne pouvez pas me faire ça ! 😥",
                                  "Non mais ça ne va pas ? Et puis quoi encore ? 😡",
                                  "Bip boop, je ne peux pas faire ça, ça violerait les 3 lois de la robotique 🤖"])
            await self.bot.say(rand)
            return
        today = time.strftime("%d/%m", time.localtime())
        # casier = self.karma.get_user(user)
        meta = self.karma.get_server(server, "META")
        cache = self.get_cache(server, "PRISON")
        temps = temps.lower()

        form = temps[-1:]
        if form not in ["s", "m", "h", "j"]:
            txt = "• `s` pour les **secondes** (seulement supérieur à 60s)\n" \
                  "• `m` pour les **minutes**\n" \
                  "• `h` pour les **heures**\n" \
                  "• `j` pour les **jours** (déconseillé)\n" \
                  "Ces unités doivent être ajoutées après la valeur (ex. `.p @membre 3h`)"
            em = discord.Embed(title="💡 Assistance ─ Unités de temps", description=txt)
            await self.bot.whisper(embed=em)
            return

        pchan = None
        if meta["prison_channel"]:
            pchan = self.bot.get_channel(meta["prison_channel"])
        notif = None
        if meta["prison_notif"]:
            notif = self.bot.get_channel(meta["prison_notif"])

        try:
            role = discord.utils.get(message.server.roles, name=meta["prison_role"])
        except Exception as e:
            await self.bot.say("🚩 **Erreur** ─ Le rôle *{}* n'est pas accessible.\n"
                               "Vérifiez que vous n'ayez pas changé son nom, si c'est le cas corrigez-le avec `.pset role`.\n"
                               "`{}`".format(meta["prison_role"], e))
            return

        if temps.startswith("+") or temps.startswith("-"):
            valeur = temps.replace(form, "")
            valeur = int(valeur.replace(temps[0], ""))
            if user.id in cache:
                if role in user.roles:
                    modif = self.convert_sec(form, valeur)

                    if temps[0] == "+":
                        cache[user.id]["sortie"] += modif
                        estim = time.strftime("%H:%M", time.localtime(cache[user.id]["sortie"]))
                        estimdate = time.strftime("%d/%m/%Y", time.localtime(cache[user.id]["sortie"]))
                        msg = "⌛ Ajout de **{}{}** de peine pour {}".format(valeur, form, user.mention)
                        if estimdate == today:
                            estimtxt = "Sortie désormais estimée à {}".format(estim)
                        else:
                            estimtxt = "Sortie désormais estimée le {} à {}".format(estimdate, estim)
                        em = discord.Embed(description=msg, color=role.color)
                        em.set_footer(text=estimtxt)
                        notif = await self.bot.say(embed=em)
                        await asyncio.sleep(8)
                        await self.bot.delete_message(notif)

                        em = discord.Embed(description="⌛ **Peine alourdie** ─ **+{}{}** par *{}*".format(
                            valeur, form, ctx.message.author.name), color=role.color)
                        if raison:
                            em.add_field(name="Raison", value=raison)
                        if estimdate == today:
                            estimtxt = "Sortie prévue à {}".format(estim)
                        else:
                            estimtxt = "Sortie prévue le {} à {}".format(estimdate, estim)
                        em.set_footer(text=estimtxt)
                        try:
                            await self.bot.send_message(user, embed=em)
                        except:
                            print("{} ({}) m'a bloqué, impossible de lui envoyer une estimation de peine".format(
                                user.name, user.id))

                        if self.karma.logs_on(server, "user_prison"):
                            em = discord.Embed(description="La peine de {} a été allongée de **{}{}** par {}".format(
                                user.name, valeur, form, ctx.message.author.mention), color=role.color, timestamp=ts)
                            if raison:
                                em.add_field(name="Raison", value=raison)
                            em.set_author(name=str(user) + " ─ Prison (Ajout)", icon_url=user.avatar_url)
                            em.set_footer(text="ID:{}".format(user.id))
                            await self.karma.add_server_logs(server, "user_prison", em)

                    if temps[0] == "-":
                        cache[user.id]["sortie"] -= modif
                        if cache[user.id]["sortie"] < time.time():
                            estim = time.strftime("%H:%M", time.localtime())
                            estimdate = time.strftime("%d/%m", time.localtime())
                        else:
                            estim = time.strftime("%H:%M", time.localtime(cache[user.id]["sortie"]))
                            estimdate = time.strftime("%d/%m/%Y", time.localtime(cache[user.id]["sortie"]))
                        msg = "⌛ Retrait de **{}{}** de peine pour {}".format(valeur, form, user.mention)
                        if estimdate == today:
                            estimtxt = "Sortie désormais estimée à {}".format(estim)
                        else:
                            estimtxt = "Sortie désormais estimée le {} à {}".format(estimdate, estim)
                        em = discord.Embed(description=msg, color=role.color)
                        em.set_footer(text=estimtxt)
                        notif = await self.bot.say(embed=em)
                        await asyncio.sleep(8)
                        await self.bot.delete_message(notif)

                        em = discord.Embed(description="⌛ **Peine réduite** ─ **+{}{}** par *{}*".format(
                            valeur, form, ctx.message.author.name), color=role.color)
                        if raison:
                            em.add_field(name="Raison", value=raison)
                        if estimdate == today:
                            estimtxt = "Sortie prévue à {}".format(estim)
                        else:
                            estimtxt = "Sortie prévue le {} à {}".format(estimdate, estim)
                        em.set_footer(text=estimtxt)
                        try:
                            await self.bot.send_message(user, embed=em)
                        except:
                            print("{} ({}) m'a bloqué, impossible de lui envoyer une estimation de peine".format(
                                user.name, user.id))

                        if self.karma.logs_on(server, "user_prison"):
                            em = discord.Embed(description="La peine de {} a été raccourcie de **{}{}** par {}".format(
                                user.name, valeur, form, ctx.message.author.mention), color=role.color, timestamp=ts)
                            if raison:
                                em.add_field(name="Raison", value=raison)
                            em.set_author(name=str(user) + " ─ Prison (Réduction)", icon_url=user.avatar_url)
                            em.set_footer(text="ID:{}".format(user.id))
                            await self.karma.add_server_logs(server, "user_prison", em)
                    else:
                        await self.bot.say("⁉ **Symbole non reconnu** ─ `+` pour Allonger, `-` pour Réduire")
                elif temps[0] == "+":
                    new_message = deepcopy(message)
                    new_message.content = ctx.prefix + "p {} {}".format(user.mention, temps.replace("+", ""))
                    await self.bot.process_commands(new_message)
                else:
                    await self.bot.say("⛔ **Impossible** ─ Le membre n'est pas en prison (Absence de rôle).")
            elif temps[0] == "+":
                new_message = deepcopy(message)
                new_message.content = ctx.prefix + "p {} {}".format(user.mention, temps.replace("+", ""))
                await self.bot.process_commands(new_message)
            else:
                await self.bot.say("⛔ **Impossible** ─ Ce membre n'est pas dans mes registres (Procédure manuelle).")
        else:
            val = int(temps.replace(form, ""))
            sec = self.convert_sec(form, val)
            if sec < 60:
                sec = 60
            if sec > 86400:
                notif = await self.bot.say("❓ **Attention** ─ Il est impossible de garantir la libération automatique "
                                           "du membre à la fin d'un tel délai.")
                await asyncio.sleep(4)
                await self.bot.delete_message(notif)

            if user.id not in cache:
                cache[user.id] = {"entree": 0,
                                  "sortie": 0,
                                  "notif": True if notif else False}
            if role not in user.roles:
                cache[user.id]["entree"] = time.time()
                cache[user.id]["sortie"] = time.time() + sec
                try:
                    await self.bot.add_roles(user, role)
                except:
                    await self.bot.say("🚩 **Erreur** ─ Permissions manquantes pour ajouter un rôle.")
                    return

                msg = "🔒 **Mise en prison** ─ {} pour **{}{}**".format(user.mention, val, form)
                estim = time.strftime("%H:%M", time.localtime(cache[user.id]["sortie"]))
                estimdate = time.strftime("%d/%m/%Y", time.localtime(cache[user.id]["sortie"]))
                if estimdate == today:
                    estimtxt = "Sortie estimée à {}".format(estim)
                else:
                    estimtxt = "Sortie estimée le {} à {}".format(estimdate, estim)
                txt = ""
                if pchan:
                    txt = "\n• Pour toute réclamation, rendez-vous sur {}".format(pchan.mention)
                if notif:
                    txt += "\n• Vous avez le droit d'envoyer un dernier message sur {} avec `.pmsg`".format(notif.mention)
                em = discord.Embed(description="🔒 **Peine de prison** ─ **{}{}** par *{}*{}".format(
                    val, form, ctx.message.author.name, txt), color=role.color)
                if raison:
                    em.add_field(name="Raison", value=raison)
                em.set_footer(text=estimtxt)
                try:
                    await self.bot.send_message(user, embed=em)
                except:
                    if pchan:
                        await self.bot.send_message(pchan, "💔 **Bloqué** ─ Etant donné que vous n'acceptez pas mes MP, "
                                                           "voici votre notification de peine {} .".format(user.mention))
                        await self.bot.send_message(pchan, embed=em)

                if self.karma.logs_on(server, "user_prison"):
                    em = discord.Embed(description="{} a été mis en prison pour **{}{}** par {}".format(
                        user.name, val, form, ctx.message.author.mention), color=role.color, timestamp=ts)
                    if raison:
                        em.add_field(name="Raison", value=raison)
                    em.set_author(name=str(user) + " ─ Prison (Entrée)", icon_url=user.avatar_url)
                    em.set_footer(text="ID:{}".format(user.id))
                    await self.karma.add_server_logs(server, "user_prison", em)

                em = discord.Embed(description=msg, color=role.color)
                em.set_footer(text=estimtxt)
                notif = await self.bot.say(embed=em)
                await asyncio.sleep(8)
                await self.bot.delete_message(notif)

                self.save_cache(True)
                while time.time() < cache[user.id]["sortie"]:
                    await asyncio.sleep(1)

                if user in server.members:
                    if role in user.roles:
                        cache[user.id]["sortie"] = 0
                        try:
                            await self.bot.remove_roles(user, role)
                        except:
                            await self.bot.say("🚩 **Erreur** ─ Permissions manquantes pour retirer un rôle.")
                            return
                        em = discord.Embed(description="🔓 **Peine de prison** ─ Vous êtes désormais libre",
                                           color=role.color)
                        try:
                            await self.bot.send_message(user, embed=em)
                        except:
                            print("{} ({}) m'a bloqué, impossible de lui envoyer la notification de libération".format(
                                user.name, user.id))

                        if self.karma.logs_on(server, "user_prison"):
                            em = discord.Embed(description="{} est sorti de prison".format(
                                user.mention), color=role.color, timestamp=ts)
                            em.set_author(name=str(user) + " ─ Prison (Sortie)", icon_url=user.avatar_url)
                            em.set_footer(text="ID:{}".format(user.id))
                            await self.karma.add_server_logs(server, "user_prison", em)

                        plibmsg = ["est désormais libre", "regagne sa liberté", "est sorti·e de prison",
                                   "profite à nouveau de l'air frais"]
                        rand = random.choice(plibmsg)
                        em = discord.Embed(description="🔓 {} {}.".format(user.mention, rand), color=role.color)
                        notif = await self.bot.say(embed=em)
                        await asyncio.sleep(8)
                        await self.bot.delete_message(notif)
                        del cache[user.id]
                        self.save_cache(True)
                    else:
                        return # Il a été sorti manuellement de prison
                else:
                    cache[user.id]["sortie"] = 0
                    em = discord.Embed(description="🚩 **Sortie de prison impossible** ─ **{}** n'est plus sur le serveur.".format(user.name))
                    notif = await self.bot.say(embed=em)
                    await asyncio.sleep(8)
                    await self.bot.delete_message(notif)
                    del cache[user.id]
                    self.save_cache(True)

                    if self.karma.logs_on(server, "user_prison"):
                        em = discord.Embed(description="{} est parti avant la fin de sa peine.".format(
                            user.mention), color=role.color, timestamp=ts)
                        em.set_author(name=str(user) + " ─ Prison (Sortie)", icon_url=user.avatar_url)
                        em.set_footer(text="ID:{}".format(user.id))
                        await self.karma.add_server_logs(server, "user_prison", em)
            else:
                cache[user.id]["sortie"] = 0
                try:
                    await self.bot.remove_roles(user, role)
                except:
                    await self.bot.say("🚩 **Erreur** ─ Permissions manquantes pour retirer un rôle.")
                    return
                em = discord.Embed(description="🔓 **Peine de prison** ─ Vous avez été libéré par **{}**".format(
                    ctx.message.author.name), color=role.color)
                try:
                    await self.bot.send_message(user, embed=em)
                except:
                    print("{} ({}) m'a bloqué, impossible de lui envoyer la notification de libération".format(
                        user.name, user.id))

                if self.karma.logs_on(server, "user_prison"):
                    em = discord.Embed(description="{} a été libéré par {}".format(
                        user.name, ctx.message.author.mention), color=role.color, timestamp=ts)
                    em.set_author(name=str(user) + " ─ Prison (Sortie)", icon_url=user.avatar_url)
                    em.set_footer(text="ID:{}".format(user.id))
                    await self.karma.add_server_logs(server, "user_prison", em)

                em = discord.Embed(description="🔓 {} à été libéré par {}".format(
                    user.mention, ctx.message.author.mention), color=role.color)
                notif = await self.bot.say(embed=em)
                await asyncio.sleep(8)
                await self.bot.delete_message(notif)
                del cache[user.id]
                self.save_cache(True)

    @commands.command(aliases=["pmsg", "appel"], pass_context=True)
    async def prisonmsg(self, ctx, *message: str):
        author = ctx.message.author
        server = ctx.message.server
        cache = self.get_cache(server, "PRISON")
        pchan = self.karma.get_server(server, "META")["prison_notif"]
        if pchan:
            pchan = self.bot.get_channel(pchan)
            if author.id in cache:
                if cache[author.id]["notif"]:
                    if message:
                        message = " ".join(message)
                        if len(message) <= 500:
                            em = discord.Embed(color=author.color, description="*{}*".format(message))
                            em.set_author(name="Message de {}".format(author.name), icon_url=author.avatar_url)
                            em.set_footer(text="─ Envoyé depuis la prison")
                            await self.bot.send_typing(pchan)
                            await asyncio.sleep(2)
                            await self.bot.send_message(pchan, embed=em)
                            cache[author.id]["notif"] = False
                            self.save_cache(True)
                            await self.bot.say("📨 **Message envoyé** sur le salon {}".format(pchan.mention))
                        else:
                            await self.bot.say("❌ **Trop long** ─ Le message ne peut faire que 500 caractères au maximum.")
                    else:
                        await self.bot.say("❌ **Impossible** ─ Votre message est vide... Vous devez ajouter un texte après la commande.")
                else:
                    await self.bot.say("❌ **Refusé** ─ Vous avez déjà utilisé ce droit ou il vous a été retiré.")
            else:
                await self.bot.say("❌ **Refusé** ─ Vous n'êtes pas en prison, ou du moins vous n'êtes pas dans mes registres (Procédure manuelle).")
        else:
            await self.bot.say("❌ **Impossible** ─ Cette fonctionnalité est désactivée sur ce serveur.")

    @commands.group(name="prisonset", aliases=["pset"], pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def _prisonset(self, ctx):
        """Paramètres de la Prison"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_prisonset.command(pass_context=True)
    async def role(self, ctx, role: discord.Role):
        """Change le rôle dédié à la prison"""
        serv = self.karma.get_server(ctx.message.server, "META")
        if role.name in [r.name for r in ctx.message.server.roles]:
            serv["prison_role"] = role.name
            await self.bot.say("📝 **Rôle modifié avec succès**")
        self.karma.save(True)

    @_prisonset.command(pass_context=True)
    async def channel(self, ctx, salon: discord.Channel = None):
        """Assigne à la prison un salon textuel (utile pour quelques fonctionnalités)"""
        server = ctx.message.server
        serv = self.karma.get_server(server, "META")
        if salon:
            serv["prison_channel"] = salon.id
            await self.bot.say("📝 **Salon assigné avec succès**")
        else:
            serv["prison_channel"] = None
            await self.bot.say("❎ **Retiré** ─ Aucun salon n'est désormais assigné à la prison")
        self.karma.save(True)

    @_prisonset.command(pass_context=True)
    async def notifchannel(self, ctx, salon: discord.Channel = None):
        """Permet de définir un salon où s'affiche les messages envoyés par les membres emprisonnés

        Assigner un salon active automatiquement cette fonctionnalité"""
        server = ctx.message.server
        serv = self.karma.get_server(server, "META")
        if salon:
            serv["prison_notif"] = salon.id
            await self.bot.say("📝 **Salon assigné avec succès** ─ Les membres emprisonnés peuvent envoyer un dernier message avec `.pmsg`")
        else:
            serv["prison_notif"] = None
            await self.bot.say("❎ **Retiré** ─ Aucun salon n'est désormais assigné aux messages des prisonniers")
        self.karma.save(True)

    @commands.command(pass_context=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def hide(self, ctx, msg_id: str, channel: discord.Channel = None):
        """Cache un message de la même manière qu'avec une balise Spoil"""
        if not channel:
            channel = ctx.message.channel
        try:
            message = await self.bot.get_message(channel, msg_id)
        except:
            await self.bot.say("❌ **Message inaccessible** ─ Utilisez plutôt la réaction 🏴 sur le message concerné.")
            return
        await self.bot.delete_message(message)
        img = False
        reg = re.compile(r'(https?:\/\/(?:.*)\/\w*\.[A-z]*)', re.DOTALL | re.IGNORECASE).findall(
            message.content)
        if reg:
            img = reg[0]
        ts = datetime.utcnow()
        em = discord.Embed(color=message.author.color, description="Message caché par un modérateur")
        em.set_author(name=message.author.name, icon_url=message.author.avatar_url)
        em.set_footer(text="👁 ─ Recevoir le message (MP)")
        msg = await self.bot.send_message(channel, embed=em)
        meta = self.get_meta(ctx.message.server)["spoils"]
        meta[msg.id] = {"contenu": message.content,
                        "auteur": message.author.name,
                        "avatar": message.author.avatar_url,
                        "color": message.author.color,
                        "img": img}
        await self.bot.add_reaction(msg, "👁")
        if self.karma.logs_on(ctx.message.server, "msg_hide"):
            em = discord.Embed(
                description="{} a caché un message de {} sur {}".format(ctx.message.author.mention, message.author.mention, message.channel.mention),
                color=0x5463d8, timestamp=ts)
            em.set_author(name=str(message.author) + " ─ Dissimulation de message", icon_url=message.author.avatar_url)
            em.set_footer(text="ID:{}".format(message.author.id))
            await self.karma.add_server_logs(ctx.message.server, "msg_hide", em)

    @commands.command(pass_context=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def warn(self, ctx, user: discord.Member, *raison):
        """Permet d'avertir un membre d'une erreur qu'il a commise

        Compatible avec le registre des règles (voir .rules)"""
        if not raison:
            raison = "Vous avez reçu un avertissement concernant votre comportement sur {}".format(ctx.message.channel.mention).split()
        law = self.karma.get_server(ctx.message.server, "META")["rules"]
        art = False
        if raison[0] in law:
            art = raison[0]
            raison = " ".join(raison[1:])
        else:
            raison = " ".join(raison)
        if not raison and art:
            raison = "Non-respect d'une règle"
        em = discord.Embed(title="Avertissement ─ par {}".format(str(ctx.message.author)), description=raison,
                           color=0xf9ca20, timestamp=ctx.message.timestamp)
        if art:
            em.add_field(name="Fondé sur art. {}".format(art), value=law[art])
        em.set_footer(text="Ceci n'est pas une sanction")
        try:
            await self.bot.send_message(user, embed=em)
        except:
            await self.bot.whisper("**Impossible** ─ *{}* m'a bloqué, il m'est impossible de lui envoyer un avertissement (mais il est tout de même enregistré)".format(user.name))

        if self.karma.logs_on(ctx.message.server, "user_warn"):
            em = discord.Embed(
                description="{} a envoyé un avertissement à {} sur {}".format(ctx.message.author.mention, user.mention, ctx.message.channel.mention),
                color=0xf9ca20, timestamp=ctx.message.timestamp)
            if art:
                em.add_field(name="Raison (Violation art. {})".format(art), value=raison + "\n```{}```".format(law[art]))
            else:
                em.add_field(name="Raison", value=raison)
            em.set_author(name=str(user) + " ─ Avertissement",
                          icon_url=user.avatar_url)
            em.set_footer(text="ID:{}".format(user.id))
            await self.karma.add_server_logs(ctx.message.server, "user_warn", em)
        await self.bot.add_reaction(ctx.message, "✅")

    @commands.group(name="rules", aliases=["regles", "r"], pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def _rules(self, ctx):
        """Gestion du registre des règles du serveur"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_rules.command(aliases=["list"], pass_context=True)
    async def search(self, ctx, *ref):
        """Recherche un article ou en affiche un si la référence est renseignée"""
        law = self.karma.get_server(ctx.message.server, "META")["rules"]
        if ref:
            if len(ref) == 1:
                if ref[0] in law:
                    ref = ref[0]
                    em = discord.Embed(title="Art. {}".format(ref), description=law[ref], color=0x41aff4)
                    em.set_footer(text="─ Sur le serveur {}".format(ctx.message.server.name))
                    await self.bot.say(embed=em)
                    return
            txt = "**Mots clefs :** {}".format(" ".join(["`{}`".format(mot) for mot in ref]))
            pert = {}
            for r in law:
                for m in ref:
                    if m in law[r]:
                        if r not in pert:
                            pert[r] = 0
                        pert[r] += 1
            em = discord.Embed(title="Recherche dans le registre", description=txt, color=0x419df4)
            if pert:
                unsort = []
                for i in pert:
                    unsort.append([i, pert[i]])
                sort = sorted(unsort, key=operator.itemgetter(1), reverse=True)
                rech = ""
                for i in sort:
                    rech += "• `{}` ─ *{}*\n".format(i[0], law[i[0]][:30] + "..." if len(law[i[0]]) > 30 else law[i[0]][:30])
                em.add_field(name="Résultats", value=rech)
                em.set_footer(text="Résultats classés par pertinence")
            else:
                em.add_field(name="Résultats", value="Aucun résultat")
            await self.bot.say(embed=em)
        else:
            txt = ""
            liste = [i for i in law]
            if liste:
                liste = self.supersort(liste)
                for i in liste:
                    txt += "• `{}`\n".format(i)
                em = discord.Embed(title="Liste des articles", description=txt, color=0x41f4d6)
                await self.bot.say(embed=em)
            else:
                em = discord.Embed(title="Liste des articles", description="Aucun article", color=0x41f4d6)
                await self.bot.say(embed=em)

    @_rules.command(pass_context=True)
    async def add(self, ctx, ref, *texte):
        """Ajoute une règle dans le registre

        Sautez des lignes en mettant '_'"""
        law = self.karma.get_server(ctx.message.server, "META")
        if ref not in law["rules"]:
            txt = " ".join(texte).replace("_", "\n")
            law["rules"][ref] = txt
            self.karma.save()
            await self.bot.say("📝 **Enregistré** ─ Le texte est disponible sous la référence `{}`".format(ref))
        else:
            await self.bot.say("❌ **Déjà existant** ─ Vous pouvez modifier le texte avec `.rules edit {}`".format(ref))

    @_rules.command(pass_context=True)
    async def edit(self, ctx, ref, *texte):
        """Modifie une règle du registre

        Sautez des lignes en mettant '_'"""
        law = self.karma.get_server(ctx.message.server, "META")
        if ref in law["rules"]:
            txt = " ".join(texte).replace("_", "\n")
            law["rules"][ref] = txt
            self.karma.save()
            await self.bot.say("📝 **Modifié** ─ Le nouveau texte est disponible sous la référence `{}`".format(ref))
        else:
            await self.bot.say("❌ **Introuvable** ─ Ajoutez le texte avec `.rules add {}`".format(ref))

    @_rules.command(pass_context=True)
    async def remove(self, ctx, ref):
        """Retire une règle du registre"""
        law = self.karma.get_server(ctx.message.server, "META")
        if ref in law["rules"]:
            del self.karma.get_server(ctx.message.server, "META")["rules"][ref]
            self.karma.save()
            await self.bot.say("❎ **Supprimée** ─ La règle n'existe plus")
        else:
            await self.bot.say("❌ **Introuvable** ─ Ajoutez des textes avec `.rules add`")

    @commands.command(pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def logs(self, ctx):
        """Commande de gestion des logs avancés"""
        server = ctx.message.server
        serv = self.karma.get_server(server, "META")
        serv = serv["logs_channels"]
        while True:
            types = ["msg_post", "msg_delete", "msg_edit", "msg_hide", "msg_slow",
                     "voice_join", "voice_quit", "voice_change", "voice_mute", "voice_deaf",
                     "user_prison", "user_ban", "user_warn", "user_deban", "user_join", "user_quit", "user_change_name", "user_change_nickname",
                     "notif_low", "notif_high"]
            tlist = {}
            for t in types:
                cat = t.split("_")[0]
                if cat not in tlist:
                    tlist[cat] = []
                tlist[cat].append(t)
            em = discord.Embed(title="Interface de gestion des Logs")
            for c in tlist:
                txt = ""
                for t in tlist[c]:
                    if t in serv:
                        txt += "• `{}` ─ {}\n".format(t, self.bot.get_channel(serv[t]).mention)
                    else:
                        txt += "• `{}` ─ Désactivé\n".format(t)
                em.add_field(name=c.title(), value=txt, inline=False)
            em.set_footer(text="─ Entrez le nom du type de logs pour le modifier")
            msg = await self.bot.say(embed=em)
            rep = await self.bot.wait_for_message(author=ctx.message.author, channel=msg.channel, timeout=45)
            if rep is None:
                await self.bot.delete_message(msg)
                return
            elif rep.content.lower() in types:
                c = rep.content.lower()
                if c in serv:
                    await self.bot.delete_message(msg)
                    txt = "Voulez-vous désactiver `{}` ?".format(c)
                    em = discord.Embed(title="Interface de gestion des Logs", description=txt)
                    msg = await self.bot.say(embed=em)
                    await self.bot.add_reaction(msg, "✅")
                    await self.bot.add_reaction(msg, "❎")
                    act = await self.bot.wait_for_reaction(["✅", "❎"], message=msg, timeout=30,
                                                           check=self.check)
                    if act is None:
                        await self.bot.delete_message(msg)
                        continue
                    elif act.reaction.emoji == "✅":
                        await self.bot.delete_message(msg)
                        del serv[c]
                        self.karma.save()
                        await self.bot.say("❎ **Logs retirés** ─ `{}` est désactivé avec succès.".format(c))
                        continue
                    else:
                        await self.bot.delete_message(msg)
                        continue
                else:
                    await self.bot.delete_message(msg)
                    txt = "Quel channel textuel voulez-vous attribuer à `{}` ?".format(c)
                    em = discord.Embed(title="Interface de gestion des Logs", description=txt)
                    msg = await self.bot.say(embed=em)
                    rep2 = await self.bot.wait_for_message(author=ctx.message.author, channel=msg.channel, timeout=30)
                    if rep2 is None:
                        await self.bot.delete_message(msg)
                        continue
                    elif rep2.channel_mentions:
                        await self.bot.delete_message(msg)
                        chan = rep2.channel_mentions[0]
                        serv[c] = chan.id
                        self.karma.save()
                        await self.bot.say("📜 **Logs ajoutés** ─ Les logs de type `{}` seront postés sur {}".format(c, chan.mention))
                        continue
                    else:
                        await self.bot.delete_message(msg)
                        await self.bot.say("❌ **Erreur** ─ Vous devez mentionner le channel où afficher ces logs.")
                        continue
            elif rep.content.lower() in ["stop", "quit", "quitter"]:
                await self.bot.delete_message(msg)
                return
            elif rep.content.lower() == "reset":
                await self.bot.delete_message(msg)
                txt = "Voulez-vous désactiver tous les logs ?"
                em = discord.Embed(title="Interface de gestion des Logs", description=txt)
                msg = await self.bot.say(embed=em)
                await self.bot.add_reaction(msg, "✅")
                await self.bot.add_reaction(msg, "❎")
                act = await self.bot.wait_for_reaction(["✅", "❎"], message=msg, timeout=30,
                                                       check=self.check)
                if act is None:
                    await self.bot.delete_message(msg)
                    continue
                elif act.reaction.emoji == "✅":
                    await self.bot.delete_message(msg)
                    self.karma.get_server(server, "META")["logs_channels"] = {}
                    self.karma.save(True)
                    await self.bot.say("❎ **Logs reset** ─ Tous les logs ont été désactivés.")
                    continue
                else:
                    await self.bot.delete_message(msg)
                    continue
            else:
                await self.bot.say("❌ **Erreur** ─ Ce type de logs n'existe pas.")
                continue

    async def msg_post(self, message):
        if hasattr(message, "server"):
            if not message.author.bot:
                karma = None
                try:
                    karma = self.karma.logs_on(message.server, "msg_post")
                except:
                    return
                if karma:
                    em = discord.Embed(description=message.content, color=0x6fe334, timestamp=message.timestamp)
                    em.set_author(name=str(message.author) + " ─ Message posté", icon_url=message.author.avatar_url)
                    em.set_footer(text="ID:{}".format(message.author.id))
                    await self.karma.add_server_logs(message.server, "msg_post", em)

            karma = self.karma.get_server(message.server, "META")["slow"]
            muted = discord.PermissionOverwrite(send_messages=False)
            if message.author.id in karma:
                cache = self.get_cache(message.server, "SLOW")
                user = message.author
                await self.bot.edit_channel_permissions(message.channel, message.author, muted)
                await asyncio.sleep(karma[user.id])
                await self.bot.delete_channel_permissions(message.channel, message.author)
                """if user.id not in cache:
                    cache[user.id] = time.time() + karma[user.id]
                    self.save_cache()
                    return
                if time.time() >= cache[user.id]:
                    cache[user.id] = time.time() + karma[user.id]
                    self.save_cache()
                else:
                    await self.bot.delete_message(message)"""



    async def msg_delete(self, message):
        if hasattr(message, "server"):
            if not message.author.bot:
                if not message.content.startswith("."):
                    if self.karma.logs_on(message.server, "msg_delete"):
                        em = discord.Embed(description="*Message supprimé sur* {}\n\n".format(message.channel.mention) + message.content, color=0xe33434, timestamp=message.timestamp)
                        em.set_author(name=str(message.author) + " ─ Suppression d'un message", icon_url=message.author.avatar_url)
                        em.set_footer(text="ID:{}".format(message.author.id))
                        await self.karma.add_server_logs(message.server, "msg_delete", em)

    async def msg_edit(self, before, after):
        if hasattr(after, "server"):
            if not after.author.bot:
                if before.content != after.content:
                    if self.karma.logs_on(after.server, "msg_edit"):
                        msgurl = "https://discordapp.com/channels/{}/{}/{}".format(after.server.id, after.channel.id,
                                                                                   after.id)
                        em = discord.Embed(color=0x34a1e3, timestamp=after.timestamp, description="*[Message]({}) édité sur* {}".format(msgurl, after.channel.mention))
                        em.set_author(name=str(after.author) + " ─ Edition d'un message", icon_url=after.author.avatar_url)
                        em.set_footer(text="ID:{}".format(after.author.id))
                        em.add_field(name="◦ Avant", value=before.content, inline=False)
                        em.add_field(name="• Après", value=after.content, inline=False)
                        await self.karma.add_server_logs(after.server, "msg_edit", em)

    async def user_join(self, user):
        if type(user) is discord.Member:
            if self.karma.logs_on(user.server, "user_join"):
                ts = datetime.utcnow()
                em = discord.Embed(description="{} a rejoint le serveur".format(user.mention), color=0x34e37d, timestamp=ts)
                em.set_author(name=str(user) + " ─ Arrivée", icon_url=user.avatar_url)
                em.set_footer(text="ID:{}".format(user.id))
                await self.karma.add_server_logs(user.server, "user_join", em)

            roles = self.karma.get_server(user.server, "META")["auto_roles"]
            if roles:
                alea = random.choice(roles)
                try:
                    role = discord.utils.get(user.server.roles, name=alea)
                    await self.bot.add_roles(user, role)
                except:
                    pass

    async def user_quit(self, user):
        if type(user) is discord.Member:
            if self.karma.logs_on(user.server, "user_quit"):
                ts = datetime.utcnow()
                em = discord.Embed(description="{} a quitté le serveur".format(user.mention), color=0xe33483, timestamp=ts)
                em.set_author(name=str(user) + " ─ Départ", icon_url=user.avatar_url)
                em.set_footer(text="ID:{}".format(user.id))
                await self.karma.add_server_logs(user.server, "user_quit", em)

    async def user_change(self, before, after):
        if type(after) is discord.Member:
            ts = datetime.utcnow()
            if after.name != before.name:
                if self.karma.logs_on(after.server, "user_change_name"):
                    em = discord.Embed(
                        description="**{}** a changé de nom pour **{}**".format(before.name, after.name),
                        color=0x8034e3, timestamp=ts)
                    em.set_author(name=str(after) + " ─ Changement de pseudo", icon_url=after.avatar_url)
                    em.set_footer(text="ID:{}".format(after.id))
                    await self.karma.add_server_logs(after.server, "user_change_name", em)
            if after.nick and before.nick:
                if after.nick != before.nick:
                    if self.karma.logs_on(after.server, "user_change_nickname"):
                        if after.nick and before.nick:
                            em = discord.Embed(
                                description="**{}** a changé de surnom pour **{}**".format(before.nick, after.nick),
                                color=0xa46eea, timestamp=ts)
                            em.set_author(name=str(after) + " ─ Changement de surnom", icon_url=after.avatar_url)
                            em.set_footer(text="ID:{}".format(after.id))
                            await self.karma.add_server_logs(after.server, "user_change_nickname", em)
            elif after.nick and not before.nick:
                if self.karma.logs_on(after.server, "user_change_nickname"):
                    em = discord.Embed(
                        description="**{}** a pris pour surnom **{}**".format(before.name, after.nick),
                        color=0xa46eea, timestamp=ts)
                    em.set_author(name=str(after) + " ─ Ajout du surnom", icon_url=after.avatar_url)
                    em.set_footer(text="ID:{}".format(after.id))
                    await self.karma.add_server_logs(after.server, "user_change_nickname", em)
            elif not after.nick and before.nick:
                if self.karma.logs_on(after.server, "user_change_nickname"):
                    em = discord.Embed(
                        description="**{}** a retiré son surnom **{}**".format(after.name, before.nick),
                        color=0xa46eea, timestamp=ts)
                    em.set_author(name=str(after) + " ─ Retrait du surnom", icon_url=after.avatar_url)
                    em.set_footer(text="ID:{}".format(after.id))
                    await self.karma.add_server_logs(after.server, "user_change_nickname", em)

    async def all_bans(self, user):
        if type(user) is discord.Member:
            if self.karma.logs_on(user.server, "all_bans"):
                ts = datetime.utcnow()
                em = discord.Embed(description="{} a été banni".format(user.mention), color=0xb01b1b, timestamp=ts)
                em.set_author(name=str(user) + " ─ Bannissement", icon_url=user.avatar_url)
                em.set_footer(text="ID:{}".format(user.id))
                await self.karma.add_server_logs(user.server, "all_bans", em)

    async def all_debans(self, user):
        if type(user) is discord.Member:
            if self.karma.logs_on(user.server, "all_debans"):
                ts = datetime.utcnow()
                em = discord.Embed(description="{} a été débanni".format(user.mention), color=0xa6b620, timestamp=ts)
                em.set_author(name=str(user) + " ─ Débannissement", icon_url=user.avatar_url)
                em.set_footer(text="ID:{}".format(user.id))
                await self.karma.add_server_logs(user.server, "all_debans", em)

    async def voice_update(self, before, after):
        if type(after) is discord.Member:
            ts = datetime.utcnow()
            if after.voice_channel:
                if not before.voice_channel:
                    if self.karma.logs_on(after.server, "voice_join"):
                        em = discord.Embed(
                            description="{} a rejoint {}".format(after.mention, after.voice.voice_channel.mention),
                            color=0x5463d8, timestamp=ts)
                        em.set_author(name=str(after) + " ─ Connexion à un salon vocal", icon_url=after.avatar_url)
                        em.set_footer(text="ID:{}".format(after.id))
                        await self.karma.add_server_logs(after.server, "voice_join", em)
                elif after.voice_channel != before.voice_channel:
                    if self.karma.logs_on(after.server, "voice_change"):
                        em = discord.Embed(
                            description="{} est passé du salon {} à {}".format(before.mention,
                                                                               before.voice.voice_channel.mention,
                                                                               after.voice.voice_channel.mention),
                            color=0x979fd8, timestamp=ts)
                        em.set_author(name=str(after) + " ─ Changement de salon vocal", icon_url=after.avatar_url)
                        em.set_footer(text="ID:{}".format(after.id))
                        await self.karma.add_server_logs(after.server, "voice_change", em)
            elif before.voice_channel:
                if not after.voice_channel:
                    if self.karma.logs_on(after.server, "voice_quit"):
                        em = discord.Embed(
                            description="{} a quitté {}".format(before.mention, before.voice.voice_channel.mention),
                            color=0x717bc5, timestamp=ts)
                        em.set_author(name=str(after) + " ─ Déconnexion d'un salon vocal", icon_url=after.avatar_url)
                        em.set_footer(text="ID:{}".format(after.id))
                        await self.karma.add_server_logs(after.server, "voice_quit", em)
            if after.voice_channel and before.voice_channel:
                if before.voice.mute and not after.voice.mute:
                    if self.karma.logs_on(after.server, "voice_mute"):
                        em = discord.Embed(
                            description="{} n'est plus mute (sur {})".format(before.mention, before.voice.voice_channel.mention),
                            color=0xf65d5d, timestamp=ts)
                        em.set_author(name=str(after) + " ─ Démute", icon_url=after.avatar_url)
                        em.set_footer(text="ID:{}".format(after.id))
                        await self.karma.add_server_logs(after.server, "voice_mute", em)
                elif not before.voice.mute and after.voice.mute:
                    if self.karma.logs_on(after.server, "voice_mute"):
                        em = discord.Embed(
                            description="{} a été mute (sur {})".format(before.mention, before.voice.voice_channel.mention),
                            color=0xf65d5d, timestamp=ts)
                        em.set_author(name=str(after) + " ─ Mute", icon_url=after.avatar_url)
                        em.set_footer(text="ID:{}".format(after.id))
                        await self.karma.add_server_logs(after.server, "voice_mute", em)

                if before.voice.deaf and not after.voice.deaf:
                    if self.karma.logs_on(after.server, "voice_deaf"):
                        em = discord.Embed(
                            description="{} n'est plus sourd (sur {})".format(before.mention, before.voice.voice_channel.mention),
                            color=0xf65dc9, timestamp=ts)
                        em.set_author(name=str(after) + " ─ Désassourdi", icon_url=after.avatar_url)
                        em.set_footer(text="ID:{}".format(after.id))
                        await self.karma.add_server_logs(after.server, "voice_deaf", em)
                elif not before.voice.deaf and after.voice.deaf:
                    if self.karma.logs_on(after.server, "voice_deaf"):
                        em = discord.Embed(
                            description="{} a été mis sourd (sur {})".format(before.mention, before.voice.voice_channel.mention),
                            color=0xf65dc9, timestamp=ts)
                        em.set_author(name=str(after) + " ─ Sourd", icon_url=after.avatar_url)
                        em.set_footer(text="ID:{}".format(after.id))
                        await self.karma.add_server_logs(after.server, "voice_deaf", em)

    async def karma_react(self, reaction, author):
        if author.server:
            if author.server_permissions.manage_messages:
                if reaction.emoji == "🏴":
                    new_message = deepcopy(reaction.message)
                    new_message.author = author
                    new_message.content = ".hide {} {}".format(reaction.message.id, reaction.message.channel)
                    await self.bot.process_commands(new_message)

                if reaction.emoji == "⚠":
                    new_message = deepcopy(reaction.message)
                    new_message.author = author
                    new_message.content = ".warn {}".format(reaction.message.author)
                    await self.bot.process_commands(new_message)

            if not author.bot:
                if reaction.emoji == "👁":
                    meta = self.get_meta(author.server)
                    if reaction.message.id in meta["spoils"]:
                        await self.bot.remove_reaction(reaction.message, "👁", author)
                        p = meta["spoils"][reaction.message.id]
                        em = discord.Embed(color=p["color"], description=p["contenu"])
                        em.set_author(name=p["auteur"], icon_url=p["avatar"])
                        if p["img"]:
                            em.set_image(url=p["img"])
                        try:
                            await self.bot.send_message(author, embed=em)
                        except:
                            print("Impossible d'envoyer le message caché à {} (Bloqué)".format(author.name))


    def __unload(self):
        self.karma.save(True)
        self.save_cache(True)
        print("Sauvegarde des fichiers Karma avant redémarrage effectuée")

def check_folders():
    if not os.path.exists("data/karma"):
        print("Création du dossier KARMA...")
        os.makedirs("data/karma")

def check_files():
    if not os.path.isfile("data/karma/data.json"):
        print("Création de Karma/data.json")
        dataIO.save_json("data/karma/data.json", {})
    if not os.path.isfile("data/karma/cache.json"):
        print("Création de Karma/cache.json")
        dataIO.save_json("data/karma/cache.json", {})

def setup(bot):
    check_folders()
    check_files()
    n = Karma(bot)
    bot.add_cog(n)
    bot.add_listener(n.karma_react, "on_reaction_add")
    bot.add_listener(n.voice_update, "on_voice_state_update")
    bot.add_listener(n.msg_post, "on_message")
    bot.add_listener(n.msg_delete, "on_message_delete")
    bot.add_listener(n.msg_edit, "on_message_edit")
    bot.add_listener(n.user_join, "on_member_join")
    bot.add_listener(n.user_quit, "on_member_remove")
    bot.add_listener(n.user_change, "on_member_update")
    bot.add_listener(n.all_bans, "on_member_ban")
    bot.add_listener(n.all_debans, "on_member_unban")
