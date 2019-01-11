# Ce module est volontairement excessivement commenté afin d'aider les débutants à décoder le code plus facilement
import operator
import os
import re
import time
from collections import namedtuple
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from .utils import checks
from .utils.dataIO import dataIO, fileIO


class MajorAPI:
    """API Major ─ Module social & statistique"""
    def __init__(self, bot, path):
        self.bot = bot
        self.data = dataIO.load_json(path)
        self.meta = {"lastsave": 0}

    def save(self, force: bool=False):
        """Sauvegarde les données de l'API"""
        if force:
            fileIO("data/major/data.json", "save", self.data)
        elif (time.time() - self.meta["lastsave"]) >= 180:  # 3 minutes
            fileIO("data/major/data.json", "save", self.data)
            self.meta["lastsave"] = time.time()

    def reset(self, server: discord.Server = None):
        if not server:
            fileIO("data/major/data.json", "save", {})
            self.data = {}
        else:
            if server.id in self.data:
                del self.data[server.id]
                fileIO("data/major/data.json", "save", self.data)
            else:
                return False
        return True

    def get_server(self, server: discord.Server, subdict: str= None):
        """Retourne les données d'un serveur et créée un placeholder si besoin"""
        if server.id not in self.data:
            self.data[server.id] = {"USERS": {},
                                    "GLOBALSTATS": {},
                                    "SETTINGS": {}}
            self.save(True)
        return self.data[server.id][subdict] if subdict else self.data[server.id]

    def get_account(self, user: discord.Member, subdict: str = None):
        """Retourne les données d'un membre sur un serveur"""
        if type(user) is discord.Member:
            data = self.get_server(user.server, "USERS")
            if user.id not in data:
                data[user.id] = self.new_empty_account()
                self.save()
            return data[user.id][subdict] if subdict else data[user.id]
        return {}

    def new_empty_account(self):
        """Retourne un profil videé"""
        dict = {"DATA": {"msg_nb": 0,
                         "msg_suppr": 0,
                         "emojis": {},
                         "join": 0,
                         "quit": 0,
                         "pseudos": [],
                         "surnoms": [],
                         "flammes": [],
                         "first_msg": time.time()},
                "LOGS": [],
                "PERSO": {"bottom_img": None,
                          "bar_color": None,
                          "bio": ""},
                "SYS": {"old_roles": []}}
        return dict

    def offline_get_account(self, server: discord.Server, user: discord.User):
        data = self.get_server(server, "USERS")
        if user.id not in data:
            data[user.id] = self.new_empty_account()
            self.save()
        return data[user.id]

    def logs_add(self, user: discord.Member, event: str):
        """Ajoute des logs à un membre"""
        jour, heure = time.strftime("%d/%m/%Y", time.localtime()),  time.strftime("%H:%M", time.localtime())
        logs = self.get_account(user, "LOGS")
        logs.append([heure, jour, event])
        if len(logs) > 30: logs = logs[-30:]
        return [heure, jour, event]

    def get_status_img(self, user: discord.Member):
        """Retourne l'image liée au status"""
        if user.bot:
            return "https://i.imgur.com/yYs0nOp.png"
        elif user.status == discord.Status.online:
            return "https://i.imgur.com/ksfM3FB.png"
        elif user.status == discord.Status.idle:
            return "https://i.imgur.com/5MtPQnx.png"
        elif user.status == discord.Status.dnd:
            return "https://i.imgur.com/lIgbA6x.png"
        else:
            return "https://i.imgur.com/4VwoVqY.png"

    def get_formatted_data(self, user: discord.Member):
        """Renvoie les données formattées d'un membre"""
        ajd = time.strftime("%d/%m/%Y", time.localtime())
        data = self.get_account(user)
        desc = data["PERSO"]["bio"]
        image = data["PERSO"]["bottom_img"]
        color = data["PERSO"]["bar_color"] if data["PERSO"]["bar_color"] else user.color
        # crea_date, crea_jours = user.created_at.strftime("%d/%m/%Y"), (datetime.now() - user.created_at).days
        # ariv_date, ariv_jours = user.joined_at.strftime("%d/%m/%Y"), (datetime.now() - user.joined_at).days
        firstmsg = datetime.fromtimestamp(data["DATA"]["first_msg"])
        fmsg_date, fmsg_jours = firstmsg.strftime("%d/%m/%Y"), (datetime.now() - firstmsg).days
        flammes = len(data["DATA"]["flammes"])
        der_msg = data["DATA"]["flammes"][-1] if flammes else ajd
        xp = (int(fmsg_jours) + int((datetime.now() - user.joined_at).days / 5)) * data["DATA"]["msg_nb"]
        xp = xp/(datetime.now() - user.server.created_at).days
        logs = data["LOGS"][::-1]
        pseudos, surnoms = data["DATA"]["pseudos"][::-1], data["DATA"]["surnoms"][::-1]
        StatsData = namedtuple('StatsData', ['msg_nb', 'msg_suppr', 'emojis', 'join', 'quit', 'pseudos', 'surnoms',
                                             'flammes', 'dernier_msg', 'first_msg_date', 'first_msg_jours'])
        sd = StatsData(data["DATA"]["msg_nb"], data["DATA"]["msg_suppr"], data["DATA"]["emojis"], data["DATA"]["join"],
                       data["DATA"]["quit"], pseudos, surnoms, flammes, der_msg, fmsg_date, fmsg_jours)
        status = self.get_status_img(user)
        FormattedData = namedtuple('FormattedData', ['user', 'data', 'logs', 'bio', 'image', 'color', 'status', 'xp'])
        return FormattedData(user, sd, logs, desc, image, color, status, xp)

    def get_top_xp(self, server: discord.Server, top: int):
        if server.id in self.data:
            mb = [n.id for n in server.members]
            liste = []
            for u in self.data[server.id]["USERS"]:
                try:
                    user = server.get_member(u)
                    data = self.data[server.id]["USERS"][u]
                    firstmsg = datetime.fromtimestamp(data["DATA"]["first_msg"])
                    fmsg_jours = (datetime.now() - firstmsg).days
                    xp = (int(fmsg_jours) + int((datetime.now() - user.joined_at).days / 5)) * data["DATA"]["msg_nb"]
                    xp = xp/(datetime.now() - server.created_at).days
                    liste.append([xp, u])
                except:
                    pass
            sort = sorted(liste, key=operator.itemgetter(0), reverse=True)
            return sort[:top]
        return False

class Major:
    """Major ─ Module social & statistique"""
    def __init__(self, bot):
        self.bot = bot
        self.mjr = MajorAPI(bot, "data/major/data.json")

    @commands.group(name="carte", aliases=["c", "card"], pass_context=True, invoke_without_command=True, no_pm=True)
    async def _carte(self, ctx, membre: discord.Member = None):
        """Carte de membre et commandes associées

        -> En absence de mention, renvoie la carte du membre invocateur"""
        if ctx.invoked_subcommand is None:
            if not membre:
                membre = ctx.message.author
            await ctx.invoke(self.disp, user=membre)

    @_carte.command(aliases=["card", "c"], pass_context=True, no_pm=True)
    async def disp(self, ctx, user: discord.Member = None):
        """Affiche la carte de membre sur le serveur"""
        user = user if user else ctx.message.author
        today = time.strftime("%d/%m/%Y", time.localtime())
        now = time.strftime("%H:%M", time.localtime())
        data = self.mjr.get_formatted_data(user)
        crea_date, crea_jours = user.created_at.strftime("%d/%m/%Y"), (datetime.now() - user.created_at).days
        ariv_date, ariv_jours = user.joined_at.strftime("%d/%m/%Y"), (datetime.now() - user.joined_at).days
        title = user.name if user.display_name == user.name else "{} a.k.a. « {} »".format(user.name, user.display_name)
        em = discord.Embed(title=title, description=data.bio, color=data.color)
        em.set_thumbnail(url=user.avatar_url)
        profil = "**Création** — {} · **{}**j\n".format(crea_date, crea_jours)
        profil += "**Arrivée** — {} · **{}**j\n".format(ariv_date, ariv_jours)
        profil += "**1re trace** — {} · **{}**j\n".format(data.data.first_msg_date, data.data.first_msg_jours)
        profil += "\🔥{} — {}".format(data.data.flammes, data.data.dernier_msg)
        if user.voice.voice_channel:
            profil += "\n\🎙 Connecté sur {}".format(user.voice.voice_channel.mention)
        em.add_field(name="Profil", value=profil)
        roles = " ".join(["`{}`".format(r.name) for r in user.roles if r.name != "@everyone"])
        perms = []
        if user.server_permissions.manage_messages:
            perms.append("`Gestion des messages`")
        if user.server_permissions.kick_members:
            perms.append("`Kick`")
        if user.server_permissions.ban_members:
            perms.append("`Ban`")
        if user.server_permissions.manage_roles:
            perms.append("`Gestion des rôles`")
        if user.server_permissions.administrator:
            perms = ["`Administrateur`"]
        if perms:
            roles = roles + "\n— **Perms :** {}".format(" ".join(perms))
        em.add_field(name="Hiérarchie", value=roles if roles else "Aucun")
        logs = data.logs[-3:]
        if logs:
            hist = "— **Historique :**\n"
            for act in logs:
                if act[1] == today:
                    if act[0] == now:
                        hist += "• À l'instant · *{}*\n".format(act[2])
                    else:
                        hist += "• {} · *{}*\n".format(act[0], act[2])
                else:
                    hist += "• {} · *{}*\n".format(act[1], act[2])
            if data.data.pseudos:
                hist += "\n— **Pseudos :** {}".format(", ".join(data.data.pseudos[-3:]))
            if data.data.surnoms:
                hist += "\n— ** Surnoms: ** {}".format(", ".join(data.data.surnoms[-3:]))
        else:
            hist = "Aucun historique"
        em.add_field(name="Logs", value=hist)
        rx = " | {}".format(user.game.name) if user.game else ""
        em.set_footer(text="ID · {}{}".format(user.id, rx), icon_url=data.status)
        if data.image:
            em.set_image(url=data.image)
        await self.bot.say(embed=em)

    @_carte.command(pass_context=True)
    async def bio(self, ctx, *texte):
        """Modifier la bio de sa carte de membre"""
        data = self.mjr.get_account(ctx.message.author)
        if texte:
            if not data["PERSO"]["bio"]:
                await self.bot.say("✅ **Ajoutée** — Votre bio a été ajoutée en haut de votre carte de membre.")
            else:
                await self.bot.say("📝 **Modifiée** — La bio s'affiche en haut de votre carte de membre.")
            data["PERSO"]["bio"] = " ".join(texte)
        else:
            data["PERSO"]["bio"] = ""
            await self.bot.say("❎ **Retirée** — Aucune bio ne s'affichera sur votre carte.")
        self.mjr.save()

    @_carte.command(pass_context=True)
    async def image(self, ctx, url: str = None):
        """Modifier l'image de vitrine de sa carte"""
        data = self.mjr.get_account(ctx.message.author, "PERSO")
        if url:
            if url.endswith("gif") or url.endswith("png") or url.endswith("jpg") or url.endswith("jpeg"):
                if not data["bottom_img"]:
                    await self.bot.say("✅ **Ajoutée** — L'image s'affichera au pied de votre carte.")
                else:
                    await self.bot.say("📝 **Modifiée** — L'image s'affiche au pied de votre carte de membre.")
                data["bottom_img"] = url
                self.mjr.save()
            else:
                await self.bot.say("🚫 **Erreur** — Impossible d'atteindre l'image. Fournissez un lien direct "
                                   "(qui se termine par png, jpeg, jpg ou gif).")
        else:
            await self.bot.say("❎ **Retirée** — Aucune image ne s'affichera en bas de votre carte.")
            data["bottom_img"] = None
            self.mjr.save()

    @_carte.command(pass_context=True)
    async def couleur(self, ctx, couleur_hex: str = None):
        """Changer la couleur du bord gauche de sa carte

        Ne pas mettre de couleur affichera la couleur de votre pseudo sur le serveur"""
        data = self.mjr.get_account(ctx.message.author, "PERSO")
        col = couleur_hex
        if col:
            if "#" in col:
                col = col[1:]
            elif "0x" in col:
                col = col[2:]
            if col == "000000":
                col = "000001"
            if len(col) == 6:
                col = int(col, 16)
                data["bar_color"] = col
                em = discord.Embed(color=data["bar_color"],
                                   description="💡 **Démonstration** — Voici la couleur de votre carte\n"
                                               "*Besoin d'aide ? Allez sur* http://www.color-hex.com/")
                await self.bot.say(embed=em)
                self.mjr.save()
                return
            await self.bot.say("❗ **Erreur** — On dirait que ce n'est pas de l'hexadécimal ! "
                               "Aidez-vous avec http://www.color-hex.com/")
        else:
            data["bar_color"] = None
            self.mjr.save()
            await self.bot.say("❎ **Réinitialisée** — La couleur affichée sera celle de votre pseudo.")

    @commands.command(alises=["archs"], pass_context=True)
    async def archives(self, ctx, user_id: str):
        """Voir la carte de membre d'un membre qui n'est plus présent avec son ID"""
        serv = self.mjr.get_server(ctx.message.server, "USERS")
        if user_id in serv:
            today = time.strftime("%d/%m/%Y", time.localtime())
            now = time.strftime("%H:%M", time.localtime())
            infos = serv[user_id]
            user = await self.bot.get_user_info(user_id)

            color = infos["PERSO"]["bar_color"] if infos["PERSO"]["bar_color"] else 0x000001
            firstmsg = datetime.fromtimestamp(infos["DATA"]["first_msg"])
            fmsg_date, fmsg_jours = firstmsg.strftime("%d/%m/%Y"), (datetime.now() - firstmsg).days
            flammes = len(infos["DATA"]["flammes"])
            ajd = time.strftime("%d/%m/%Y", time.localtime())
            der_msg = infos["DATA"]["flammes"][-1] if flammes else ajd
            pseudos, surnoms = infos["DATA"]["pseudos"][::-1], infos["DATA"]["surnoms"][::-1]

            em = discord.Embed(title="{}".format(user.name), description=infos["PERSO"]["bio"], color=color)
            crea_date, crea_jours = user.created_at.strftime("%d/%m/%Y"), (datetime.now() - user.created_at).days
            em.set_thumbnail(url=user.avatar_url)
            profil = "**Création** — {} · **{}**j\n".format(crea_date, crea_jours)
            profil += "**1re trace** — {} · **{}**j\n".format(fmsg_date, fmsg_jours)
            profil += "\🔥{} — {}".format(flammes, der_msg)
            em.add_field(name="Profil", value=profil)
            dlogs = infos["LOGS"][::-1]
            logs = dlogs[-3:]
            if logs:
                hist = "— **Historique :**\n"
                for act in logs:
                    if act[1] == today:
                        if act[0] == now:
                            hist += "• À l'instant · *{}*\n".format(act[2])
                        else:
                            hist += "• {} · *{}*\n".format(act[0], act[2])
                    else:
                        hist += "• {} · *{}*\n".format(act[1], act[2])
                if pseudos:
                    hist += "\n— **Pseudos :** {}".format(", ".join(pseudos[-3:]))
                if surnoms:
                    hist += "\n— ** Surnoms: ** {}".format(", ".join(surnoms[-3:]))
            else:
                hist = "Aucun historique"
            em.add_field(name="Logs", value=hist)
            em.set_footer(text="ID · {} — Archives du membre (infos. incomplètes)".format(user.id))
            await self.bot.say(embed=em)

    @commands.command(pass_context=True, no_pm=True)
    async def topxp(self, ctx, nombre: int = 20):
        """Affiche un top des membres ayant le plus d'XP"""
        server = ctx.message.server
        top = self.mjr.get_top_xp(server, nombre)
        n = 1
        txt = ""
        for i in top:
            if len(txt) > 1980:
                await self.bot.say("**Erreur** — Le nombre est trop elevé.\nEssayez avec un top plus petit.")
                return
            try:
                username = server.get_member(i[1]).name
            except:
                username = self.bot.get_user(i[1]).name
            txt += "**{}.** **{}** — {}\n".format(n, username, i[0])
            n += 1
        em = discord.Embed(title="Top des membres avec le plus d'XP", description=txt, color=0x37e1a1,
                           timestamp=ctx.message.timestamp)
        em.set_footer(text="Calculé à partir de l'activité et de l'ancienneté")
        try:
            await self.bot.whisper(embed=em)
        except:
            await self.bot.say("**Erreur** — Le nombre est trop elevé.\nEssayez avec un top plus petit.")
            return

    @commands.command(pass_context=True, hidden=True)
    @checks.admin_or_permissions(administrator=True)
    async def resetmajor(self, ctx, server_only: bool = False):
        """Reset les données (seulement de ce serveur si True)"""
        if server_only:
            self.mjr.reset(ctx.message.server)
            await self.bot.say("Serveur reset avec succès.")
        else:
            self.mjr.reset()
            await self.bot.say("Module reset avec succès.")

    @commands.command(pass_context=True, hidden=True)
    @checks.admin_or_permissions(administrator=True)
    async def sync(self, ctx, max: int, channel: discord.Channel = None):
        """Met à jour du mieux que possible les statistiques des membres de manière rétroactive du channel en cours"""
        data = self.mjr.get_server(ctx.message.server, "USERS")
        channel = channel if channel else ctx.message.channel
        n = 0
        await self.bot.say("📈 **Mise à jour des stats.** — Processus démarré")
        async for msg in self.bot.logs_from(channel, limit=max):
            if n == (0.10 * max):
                await self.bot.say("📈 **Mise à jour des stats.** — Env. 10%")
            if n == (0.25 * max):
                await self.bot.say("📈 **Mise à jour des stats.** — Env. 25%")
            if n == (0.40 * max):
                await self.bot.say("📈 **Mise à jour des stats.** — Env. 40%")
            if n == (0.65 * max):
                await self.bot.say("📈 **Mise à jour des stats.** — Env. 65%")
            if n == (0.85 * max):
                await self.bot.say("📈 **Mise à jour des stats.** — Env. 85%")
            n += 1
            try:
                user = msg.author
                if user.id not in data:
                    data[user.id] = self.mjr.new_empty_account()
                data[user.id]["DATA"]["msg_nb"] += 1
                if msg.timestamp.timestamp() < data[user.id]["DATA"]["first_msg"]:
                    data[user.id]["DATA"]["first_msg"] = msg.timestamp.timestamp()
            except:
                print("Auteur du message ID:{} introuvable".format(msg.id))
        self.mjr.save(True)
        await self.bot.say("📈 **Mise à jour des stats.** — Terminée")

    #>>>>>>>>>> EVENT TRIGGERS <<<<<<<<<<<

    async def mjr_on_msg(self, message):
        if hasattr(message, "server"):
            if message.server:
                data = self.mjr.get_account(message.author)
                if not data:
                    data = self.mjr.offline_get_account(message.server, message.author)
                date, hier = datetime.now().strftime("%d/%m/%Y"), (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
                data["DATA"]["msg_nb"] += 1
                if hier in data["DATA"]["flammes"]:
                    if date not in data["DATA"]["flammes"]:
                        data["DATA"]["flammes"].append(date)
                elif date not in data["DATA"]["flammes"]:
                    data["DATA"]["flammes"] = [date]
                self.mjr.save()

    async def mjr_on_msgdel(self, message):
        if hasattr(message, "server"):
            data = self.mjr.get_account(message.author)
            if not data:
                data = self.mjr.offline_get_account(message.server, message.author)
            data["DATA"]["msg_suppr"] += 1
            self.mjr.save()

    async def mjr_join(self, user: discord.Member):
        if type(user) is discord.Member:
            data = self.mjr.get_account(user)
            data["DATA"]["join"] += 1
            self.mjr.logs_add(user, "Entrée sur le serveur")
            self.mjr.save()

    async def mjr_quit(self, user: discord.Member):
        if type(user) is discord.Member:
            data = self.mjr.get_account(user)
            data["DATA"]["quit"] += 1
            self.mjr.logs_add(user, "Sortie du serveur")
            self.mjr.save()

    async def mjr_perso(self, before, after):
        if type(after) is discord.Member:
            data = self.mjr.get_account(after)
            if after.name != before.name:
                self.mjr.logs_add(after, "Changement de pseudo pour `{}`".format(after.name))
                if after.name not in data["DATA"]["pseudos"]:
                    data["DATA"]["pseudos"].append(after.name)
            if after.display_name != before.display_name:
                if after.display_name == after.name:
                    self.mjr.logs_add(after, "Surnom retiré")
                else:
                    self.mjr.logs_add(after, "Changement de surnom pour `{}`".format(after.display_name))
                    if after.display_name not in data["DATA"]["surnoms"]:
                        data["DATA"]["surnoms"].append(after.display_name)
            if after.avatar_url != before.avatar_url:
                url = before.avatar_url.split("?")[0]
                self.mjr.logs_add(after, "Modification de l'avatar [@]({})".format(url))
            self.mjr.save()

    async def mjr_react(self, reaction, author):
        if hasattr(author, "server"):
            if reaction.emoji == "👤":
                user = reaction.message.author
                if reaction.message.embeds:
                    embed = reaction.message.embeds[0]
                    if embed["footer"]:
                        output = re.compile(r'ID:\s?(\d*)', re.DOTALL | re.IGNORECASE).findall(embed["footer"]["text"])
                        if output:
                            user = author.server.get_member(output[0])
                today = time.strftime("%d/%m/%Y", time.localtime())
                now = time.strftime("%H:%M", time.localtime())
                data = self.mjr.get_formatted_data(user)
                crea_date, crea_jours = user.created_at.strftime("%d/%m/%Y"), (datetime.now() - user.created_at).days
                ariv_date, ariv_jours = user.joined_at.strftime("%d/%m/%Y"), (datetime.now() - user.joined_at).days
                title = user.name if user.display_name == user.name else "{} a.k.a. « {} »".format(user.name,
                                                                                                   user.display_name)
                em = discord.Embed(title=title, description=data.bio, color=data.color)
                em.set_thumbnail(url=user.avatar_url)
                profil = "**Création** — {} · **{}**j\n".format(crea_date, crea_jours)
                profil += "**Arrivée** — {} · **{}**j\n".format(ariv_date, ariv_jours)
                profil += "**1re trace** — {} · **{}**j\n".format(data.data.first_msg_date, data.data.first_msg_jours)
                profil += "\🔥{} — {}".format(data.data.flammes, data.data.dernier_msg)
                if user.voice.voice_channel:
                    profil += "\n\🎙 Connecté sur {}".format(user.voice.voice_channel.mention)
                em.add_field(name="Profil", value=profil)
                roles = " ".join(["`{}`".format(r.name) for r in user.roles if r.name != "@everyone"])
                perms = []
                if user.server_permissions.manage_messages:
                    perms.append("`Gestion des messages`")
                if user.server_permissions.kick_members:
                    perms.append("`Kick`")
                if user.server_permissions.ban_members:
                    perms.append("`Ban`")
                if user.server_permissions.manage_roles:
                    perms.append("`Gestion des rôles`")
                if user.server_permissions.administrator:
                    perms = ["`Administrateur`"]
                if perms:
                    roles = roles + "\n— **Perms :** {}".format(" ".join(perms))
                em.add_field(name="Hiérarchie", value=roles if roles else "Aucun")
                logs = data.logs[-3:]
                if logs:
                    hist = "— **Historique :**\n"
                    for act in logs:
                        if act[1] == today:
                            if act[0] == now:
                                hist += "• À l'instant · *{}*\n".format(act[2])
                            else:
                                hist += "• {} · *{}*\n".format(act[0], act[2])
                        else:
                            hist += "• {} · *{}*\n".format(act[1], act[2])
                    if data.data.pseudos:
                        hist += "\n— **Pseudos :** {}".format(", ".join(data.data.pseudos[-3:]))
                    if data.data.surnoms:
                        hist += "\n— ** Surnoms: ** {}".format(", ".join(data.data.surnoms[-3:]))
                else:
                    hist = "Aucun historique"
                em.add_field(name="Logs", value=hist)
                rx = " | {}".format(user.game.name) if user.game else ""
                em.set_footer(text="ID · {}{}".format(user.id, rx), icon_url=data.status)
                if data.image:
                    em.set_image(url=data.image)
                await self.bot.send_message(author, embed=em)

    def __unload(self):
        self.mjr.save(True)
        print("Sauvegarde de Major avant redémarrage effectuée")

#>>>>>>>>>> SYSTEMES <<<<<<<<<<<

def check_folders():
    if not os.path.exists("data/major"):
        print("Création du dossier MAJOR...")
        os.makedirs("data/major")


def check_files():
    if not os.path.isfile("data/major/data.json"):
        print("Création de Major/data.json")
        dataIO.save_json("data/major/data.json", {})


def setup(bot):
    check_folders()
    check_files()
    n = Major(bot)
    bot.add_listener(n.mjr_on_msg, "on_message")
    bot.add_listener(n.mjr_on_msgdel, "on_message_delete")
    bot.add_listener(n.mjr_join, "on_member_join")
    bot.add_listener(n.mjr_quit, "on_member_remove")
    bot.add_listener(n.mjr_perso, "on_member_update")
    bot.add_listener(n.mjr_react, "on_reaction_add")
    bot.add_cog(n)
