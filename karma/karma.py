import asyncio
import os
import random
import time
from copy import deepcopy

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

    def save(self, force: bool = False):
        if force:
            fileIO("data/karma/data.json", "save", self.data)
        elif (time.time() - self.context["last_save"]) >= 180:  # 3 minutes
            fileIO("data/karma/data.json", "save", self.data)
            self.context["last_save"] = time.time()

    def get_server(self, server: discord.Server, sub: str = None):
        if server.id not in self.data:
            opts = {"persist_roles": [],
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
        serv = self.get_server(server, "META")["logs_channels"]
        if category in serv:
            channel = self.bot.get_channel(serv[category])
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

    def save_cache(self):
        fileIO("data/karma/cache.json", "save", self.cache)
        return True

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

    @commands.command(aliases=["p"], pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def prison(self, ctx, user: discord.Member, temps: str = "10m"):
        """Emprisonne un membre pour un certain temps (def. 10m)

        <user> = Membre à emprisonner
        <temps> = Valeur suivie de l'unité (m/h/j) ou heure de sortie
        Il est possible de moduler la peine en ajoutant + et - devant la durée"""
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
        casier = self.karma.get_user(user)
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
    @checks.admin_or_permissions(manage_roles=True)
    async def logs(self, ctx):
        """Commande de gestion des logs avancés"""
        server = ctx.message.server
        serv = self.karma.get_server(server, "META")
        serv = serv["logs_channels"]
        while True:
            types = ["msg_post", "msg_delete", "msg_edit",
                     "voice_join", "voice_quit",
                     "all_bans", "all_debans",
                     "user_join", "user_quit", "user_change_name", "user_change_nickname"]
            txt = ""
            for t in types:
                if t in serv:
                    txt += "• `{}` ─ {}\n".format(t, self.bot.get_channel(serv[t]).mention)
                else:
                    txt += "• `{}` ─ Non assigné\n".format(t)
            em = discord.Embed(title="Interface de gestion des Logs", description=txt)
            em.set_footer(text="Entrez le nom du type de logs pour le modifier...")
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
            else:
                await self.bot.say("❌ **Erreur** ─ Ce type de logs n'existe pas.")
                continue

    async def msg_post(self, message):
        if hasattr(message, "server"):
            if not message.author.bot:
                if self.karma.logs_on(message.server, "msg_post"):
                    em = discord.Embed(description=message.content, color=0x87b5ff, timestamp=message.timestamp)
                    em.set_author(name=str(message.author) + " ─ Message posté", icon_url=message.author.avatar_url)
                    em.set_footer(text="ID ─ {}".format(message.author.id))
                    await self.karma.add_server_logs(message.server, "msg_post", em)

    async def msg_delete(self, message):
        if hasattr(message, "server"):
            if not message.author.bot:
                if self.karma.logs_on(message.server, "msg_delete"):
                    em = discord.Embed(description=message.content, color=0xff8787, timestamp=message.timestamp)
                    em.set_author(name=str(message.author) + " ─ Message supprimé", icon_url=message.author.avatar_url)
                    em.set_footer(text="ID ─ {}".format(message.author.id))
                    await self.karma.add_server_logs(message.server, "msg_delete", em)

    async def msg_edit(self, before, after):
        if hasattr(after, "server"):
            if not after.author.bot:
                if before.content != after.content:
                    if self.karma.logs_on(after.server, "msg_edit"):
                        em = discord.Embed(color=0x498fff, timestamp=after.timestamp, inline=False)
                        em.set_author(name=str(after.author) + " ─ Message edité", icon_url=after.author.avatar_url)
                        em.set_footer(text="ID ─ {}".format(after.author.id))
                        em.add_field(name="◦ Avant", value=before.content)
                        em.add_field(name="• Après", value=after.content)
                        await self.karma.add_server_logs(after.server, "msg_edit", em)

    async def user_join(self, user):
        if type(user) is discord.Member:
            if self.karma.logs_on(user.server, "user_join"):
                em = discord.Embed(description="{} est entré·e sur le serveur".format(user.mention), color=0x71e28f)
                em.set_author(name=str(user) + " ─ Entrée", icon_url=user.avatar_url)
                em.set_footer(text="ID ─ {}".format(user.id))
                await self.karma.add_server_logs(user.server, "user_join", em)

    async def user_quit(self, user):
        if type(user) is discord.Member:
            if self.karma.logs_on(user.server, "user_quit"):
                em = discord.Embed(description="{} est sorti·e du serveur".format(user.mention), color=0xe29c71)
                em.set_author(name=str(user) + " ─ Sortie", icon_url=user.avatar_url)
                em.set_footer(text="ID ─ {}".format(user.id))
                await self.karma.add_server_logs(user.server, "user_quit", em)

    async def user_change(self, before, after):
        if type(after) is discord.Member:
            print("Détection changement {} sur {}".format(after.name, after.server.name))
            if after.voice_channel:
                if not before.voice_channel:
                    print("Vocal - not before & after (connect)")
                    if self.karma.logs_on(after.server, "voice_join"):
                        em = discord.Embed(
                            description="{} a rejoint {}".format(after.mention, after.voice.voice_channel.mention),
                            color=0x8adb9a)
                        em.set_author(name=str(after) + " ─ Connexion à un salon vocal", icon_url=after.avatar_url)
                        em.set_footer(text="ID ─ {}".format(after.id))
                        await self.karma.add_server_logs(after.server, "voice_join", em)
            elif before.voice_channel:
                if not after.voice_channel:
                    print("Vocal - before & not after (déconnect)")
                    if self.karma.logs_on(after.server, "voice_quit"):
                        em = discord.Embed(
                            description="{} a quitté {}".format(before.mention, before.voice.voice_channel.mention),
                            color=0x5e9b6a)
                        em.set_author(name=str(after) + " ─ Déconnexion d'un salon vocal", icon_url=after.avatar_url)
                        em.set_footer(text="ID ─ {}".format(after.id))
                        await self.karma.add_server_logs(after.server, "voice_quit", em)

            if after.name != before.name:
                if self.karma.logs_on(after.server, "user_change_name"):
                    em = discord.Embed(
                        description="{} a changé de nom pour {}".format(before.name, after.name),
                        color=0xc259e5)
                    em.set_author(name=str(after) + " ─ Changement de pseudo", icon_url=after.avatar_url)
                    em.set_footer(text="ID ─ {}".format(after.id))
                    await self.karma.add_server_logs(after.server, "user_change_name", em)
            if after.display_name != before.display_name:
                if self.karma.logs_on(after.server, "user_change_nickname"):
                    if after.nick and before.nick:
                        em = discord.Embed(
                            description="{} a changé de surnom pour {}".format(before.nick, after.nick),
                            color=0xe559cd)
                        em.set_author(name=str(after) + " ─ Changement de surnom", icon_url=after.avatar_url)
                        em.set_footer(text="ID ─ {}".format(after.id))
                        await self.karma.add_server_logs(after.server, "user_change_nickname", em)

    async def all_bans(self, user):
        if type(user) is discord.Member:
            if self.karma.logs_on(user.server, "all_bans"):
                em = discord.Embed(description="{} a été banni".format(user.mention), color=0xb56767)
                em.set_author(name=str(user) + " ─ Bannissement", icon_url=user.avatar_url)
                em.set_footer(text="ID ─ {}".format(user.id))
                await self.karma.add_server_logs(user.server, "all_bans", em)

    async def all_debans(self, user):
        if type(user) is discord.Member:
            if self.karma.logs_on(user.server, "all_debans"):
                em = discord.Embed(description="{} a été débanni".format(user.mention), color=0xa34242)
                em.set_author(name=str(user) + " ─ Débannissement", icon_url=user.avatar_url)
                em.set_footer(text="ID ─ {}".format(user.id))
                await self.karma.add_server_logs(user.server, "all_debans", em)

    """async def channel_change(self, before, after):
        print("Détection changement channel {}".format(after.name))
        if after.type == discord.ChannelType.voice:
            if before.voice_members != after.voice_members:
                print("Channel {} - Changement nb de membres".format(after.name))
                diff = [x for x in before.voice_members if x not in after.voice_members] + \
                       [x for x in after.voice_members if x not in before.voice_members]
                if len(before.voice_members) < len(after.voice_members): # Connexion d'un membre
                    if self.karma.logs_on(after.server, "voice_join"):
                        for user in diff:
                            em = discord.Embed(
                                description="{} a rejoint {}".format(user.mention, after.mention),
                                color=0x8adb9a)
                            em.set_author(name=str(user) + " ─ Connexion à un salon vocal", icon_url=user.avatar_url)
                            em.set_footer(text="ID ─ {}".format(user.id))
                            await self.karma.add_server_logs(after.server, "voice_join", em)
                elif len(before.voice_members) > len(after.voice_members): # Déconnexion d'un membre
                    if self.karma.logs_on(after.server, "voice_quit"):
                        for user in diff:
                            em = discord.Embed(
                                description="{} a quitté {}".format(user.mention, after.mention),
                                color=0x8adb9a)
                            em.set_author(name=str(user) + " ─ Déconnexion d'un salon vocal", icon_url=user.avatar_url)
                            em.set_footer(text="ID ─ {}".format(user.id))
                            await self.karma.add_server_logs(after.server, "voice_quit", em)

            if after.voice_channel:
                if not before.voice_channel:
                    print("Vocal - not before & after (connect)")
                    if self.karma.logs_on(after.server, "voice_join"):
                        em = discord.Embed(
                            description="{} a rejoint {}".format(after.mention, after.voice.voice_channel.mention),
                            color=0x8adb9a)
                        em.set_author(name=str(after) + " ─ Connexion à un salon vocal", icon_url=after.avatar_url)
                        em.set_footer(text="ID ─ {}".format(after.id))
                        await self.karma.add_server_logs(after.server, "voice_join", em)
                else:
                    print("Vocal - before & after (changement)")
                    if self.karma.logs_on(after.server, "voice_join"):
                        em = discord.Embed(
                            description="{} est passé du salon {} à {}".format(before.mention,
                                                                               before.voice.voice_channel.mention,
                                                                               after.voice.voice_channel.mention),
                            color=0x5e9b6a)
                        em.set_author(name=str(after) + " ─ Changement de salon vocal", icon_url=after.avatar_url)
                        em.set_footer(text="ID ─ {}".format(after.id))
                        await self.karma.add_server_logs(after.server, "voice_join", em)
            elif before.voice_channel:
                if not after.voice_channel:
                    print("Vocal -before & not after (déconnect)")
                    if self.karma.logs_on(after.server, "voice_quit"):
                        em = discord.Embed(
                            description="{} a quitté {}".format(before.mention, before.voice.voice_channel.mention),
                            color=0x5e9b6a)
                        em.set_author(name=str(after) + " ─ Déconnexion d'un salon vocal", icon_url=after.avatar_url)
                        em.set_footer(text="ID ─ {}".format(after.id))
                        await self.karma.add_server_logs(after.server, "voice_quit", em)"""

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
    # bot.add_listener(n.channel_change, "on_channel_update")
    bot.add_listener(n.msg_post, "on_message")
    bot.add_listener(n.msg_delete, "on_message_delete")
    bot.add_listener(n.msg_edit, "on_message_edit")
    bot.add_listener(n.user_join, "on_member_join")
    bot.add_listener(n.user_quit, "on_member_remove")
    bot.add_listener(n.user_change, "on_member_update")
    bot.add_listener(n.all_bans, "on_member_ban")
    bot.add_listener(n.all_debans, "on_member_unban")
