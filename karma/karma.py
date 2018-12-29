import asyncio
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

    def update(self):
        for server in self.data:
            if not "auto_roles" in self.data[server]["META"]:
                self.data[server]["META"]["auto_roles"] = []
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
        self.meta = {}

    def save_cache(self):
        fileIO("data/karma/cache.json", "save", self.cache)
        return True

    def get_meta(self, server: discord.Server):
        if server.id not in self.meta:
            self.meta[server.id] = {"spoils": {}}
        return self.meta[server.id]

    def get_cache(self, server: discord.Server, sub: str = None):
        if server.id not in self.cache:
            self.cache[server.id] = {"PRISON": {}}
            self.save_cache()
        return self.cache[server.id][sub] if sub else self.cache[server.id]

    def check(self, reaction, user):
        return not user.bot

    def convert_sec(self, form: str, val: int):
        if form == "j":
            return val * 86400
        elif form == "h":
            return val * 3600
        elif form == "m":
            return val * 60
        else:
            return val

    @commands.command(pass_context=True)
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
    async def prison(self, ctx, user: discord.Member, temps: str = "10m"):
        """Emprisonne un membre pour un certain temps (def. 10m)

        <user> = Membre à emprisonner
        <temps> = Valeur suivie de l'unité (m/h/j) ou heure de sortie
        Il est possible de moduler la peine en ajoutant + et - devant la durée"""
        ts = datetime.utcnow()
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
                               "Vérifiez que vous n'ayez pas changé son nom, si c'est le cas corrigez-le avec `.pset role`.")
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

                        em = discord.Embed(description="La peine de {} a été allongée de **{}{}** par {}".format(
                            user.name, valeur, form, ctx.message.author.mention), color=role.color, timestamp=ts)
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

                        em = discord.Embed(description="La peine de {} a été raccourcie de **{}{}** par {}".format(
                            user.name, valeur, form, ctx.message.author.mention), color=role.color, timestamp=ts)
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
                em.set_footer(text=estimtxt)
                try:
                    await self.bot.send_message(user, embed=em)
                except:
                    if pchan:
                        await self.bot.send_message(pchan, "💔 **Bloqué** ─ Etant donné que vous n'acceptez pas mes MP, "
                                                           "voici votre notification de peine {} .".format(user.mention))
                        await self.bot.send_message(pchan, embed=em)

                em = discord.Embed(description="{} a été mis en prison pour **{}{}** par {}".format(
                    user.name, val, form, ctx.message.author.mention), color=role.color, timestamp=ts)
                em.set_author(name=str(user) + " ─ Prison (Entrée)", icon_url=user.avatar_url)
                em.set_footer(text="ID:{}".format(user.id))
                await self.karma.add_server_logs(server, "user_prison", em)

                em = discord.Embed(description=msg, color=role.color)
                em.set_footer(text=estimtxt)
                notif = await self.bot.say(embed=em)
                await asyncio.sleep(8)
                await self.bot.delete_message(notif)

                self.save_cache()
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
                        self.save_cache()
                    else:
                        return # Il a été sorti manuellement de prison
                else:
                    cache[user.id]["sortie"] = 0
                    em = discord.Embed(description="🚩 **Sortie de prison impossible** ─ **{}** n'est plus sur le serveur.".format(user.name))
                    notif = await self.bot.say(embed=em)
                    await asyncio.sleep(8)
                    await self.bot.delete_message(notif)
                    del cache[user.id]
                    self.save_cache()

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
                self.save_cache()

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
                            self.save_cache()
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
        message = self.bot.get_message(channel, msg_id)
        if message:
            await self.bot.delete_message(message)
            img = False
            reg = re.compile(r'(https?:\/\/(?:.*)\/\w*\.[A-z]*)', re.DOTALL | re.IGNORECASE).findall(
                message.content)
            if reg:
                img = reg[0]
            ts = datetime.utcnow()
            em = discord.Embed(color=message.author.color)
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
            em = discord.Embed(
                description="{} a caché un message de {} sur {}".format(ctx.message.author.mention, message.author.mention, message.channel.mention),
                color=0x5463d8, timestamp=ts)
            em.set_author(name=str(message.author) + " ─ Dissimulation de message", icon_url=message.author.avatar_url)
            em.set_footer(text="ID:{}".format(message.author.id))
            await self.karma.add_server_logs(ctx.message.server, "msg_hide", em)
        else:
            await self.bot.say("❌ **Message inaccessible** ─ Utilisez plutôt la réaction 🏴 sur le message concerné.")

    @commands.command(pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def logs(self, ctx):
        """Commande de gestion des logs avancés"""
        server = ctx.message.server
        serv = self.karma.get_server(server, "META")
        serv = serv["logs_channels"]
        while True:
            types = ["msg_post", "msg_delete", "msg_edit", "msg_hide",
                     "voice_join", "voice_quit", "voice_change", "voice_mute", "voice_deaf",
                     "user_prison", "user_ban", "user_deban", "user_join", "user_quit", "user_change_name", "user_change_nickname",
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

    async def msg_delete(self, message):
        if hasattr(message, "server"):
            if not message.author.bot:
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
                            print("Impossible d'envoyer le Spoil à {} (Bloqué)".format(author.name))

    def __unload(self):
        self.karma.save(True)
        self.save_cache()
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
