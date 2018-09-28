# Ce module est volontairement très commenté afin d'aider ceux qui s'intéresseraient au code
import os
import re
import time
from collections import namedtuple
from datetime import datetime, timedelta

import discord
from __main__ import send_cmd_help
from cogs.utils.chat_formatting import escape_mass_mentions
from discord.ext import commands

from .utils import checks
from .utils.dataIO import dataIO, fileIO


class NetworkApp:
    """API Iota Network | Extension sociale & statistique"""
    def __init__(self, bot, path):
        self.bot = bot
        self.data = dataIO.load_json(path)
        self.past_names = dataIO.load_json("data/mod/past_names.json")
        self.past_nicknames = dataIO.load_json("data/mod/past_nicknames.json")
        self.session = {"SAVETICK": 0}

    def save(self, force: bool = False):
        if force:
            fileIO("data/network/data.json", "save", self.data)
            return True
        self.session["SAVETICK"] += 1
        if self.session["SAVETICK"] == 100:
            fileIO("data/network/data.json", "save", self.data)
            self.session["SAVETICK"] = 0
        return True

    def reset(self):
        fileIO("data/network/data.json", "save", {})
        return True

    def get_server_raw_data(self, server: discord.Server, sub: str = None):
        """Retourne les données Network brut d'un serveur"""
        if server.id not in self.data:
            sysdef = {"minicard_emoji": "👤"}
            self.data[server.id] = {"SYS": sysdef,
                                    "USERS": {}}
            self.save(True)
        return self.data[server.id][sub] if sub else self.data[server.id]

    def get_account(self, user: discord.Member, sub: str = None, reset: bool = False):
        """Retourne les données Network d'un membre"""
        if hasattr(user, "server"):
            data = self.get_server_raw_data(user.server, "USERS")
            if user.id not in data or reset:
                sys = {"sync": True,
                       "_cache_games": [],
                       "save_roles": []}
                data[user.id] = {"STATS": {"msg_total": 0,
                                           "msg_suppr": 0,
                                           "emojis": {},
                                           "join": 0,
                                           "quit": 0,
                                           "ban": 0,
                                           "flammes": []},
                                 "LOGS": [],
                                 "SOCIAL": {"image": None,
                                            "color": None,
                                            "bio": None,
                                            "plus": {},
                                            "games": []},
                                 "SYS": sys,
                                 "OLDEST": time.time()}
                self.backup(user)
                self.save()
            return data[user.id][sub] if sub else data[user.id]
        return False

    def backup(self, user: discord.Member):
        """Backup les données SOCIAL d'un membre"""
        server = user.server
        b = {}
        if os.path.isfile("data/social/soc.json"):
            old = dataIO.load_json("data/social/soc.json")  # Kosmos
            if server.id in old:
                if user.id in old[server.id]:
                    b = old[server.id][user.id]
        elif os.path.isfile("data/social/user.json"):
            old = dataIO.load_json("data/social/user.json")  # EK
            if user.id in old:
                b = old[user.id]
        if b:
            u = self.get_account(user)
            # Attention, partie chiante parce que changement de noms des dicts
            u["STATS"]["msg_total"] = b["STATS"]["MSG_TOTAL"]
            u["STATS"]["msg_suppr"] = b["STATS"]["MSG_SUPPR"]
            u["STATS"]["emojis"] = b["STATS"]["EMOJIS"]
            u["STATS"]["join"] = b["STATS"]["JOIN"]
            u["STATS"]["quit"] = b["STATS"]["QUIT"]
            u["STATS"]["ban"] = b["STATS"]["BAN"]
            u["SOCIAL"]["image"] = b["SOC"]["VITRINE"]
            u["SOCIAL"]["bio"] = b["SOC"]["BIO"]
            u["LOGS"] = b["LOGS"]
            u["OLDEST"] = b["ENRG"]
            return True
        return False

    def get_raw_accounts(self, userid):
        """Renvoie tous les comptes du membre"""
        liste = []
        for serverid in self.data:
            if userid in self.data[serverid]["USERS"]:
                liste.append(self.bot.get_server(serverid))
        return liste

    def add_log(self, user: discord.Member, event: str, universal=False):
        jour = time.strftime("%d/%m/%Y", time.localtime())
        heure = time.strftime("%H:%M", time.localtime())
        p = self.get_account(user, "LOGS")
        p.append([heure, jour, event])
        if len(p) > 30:
            p = p[-30:]
        if universal:
            if self.get_account(user, "SYS")["sync"]:
                for s in self.data:
                    if user.id in self.data[s]["USERS"]:
                        self.data[s]["USERS"][user.id]["LOGS"].append([heure, jour, event])
                        if len(self.data[s]["USERS"][user.id]["LOGS"]) > 30:
                            self.data[s]["USERS"][user.id]["LOGS"] = self.data[s]["USERS"][user.id]["LOGS"][-30:]
        return True

    def sync_account(self, user: discord.Member, to_sync:str, sub_sync:str = False, force: bool = False):
        """Synchronise certains champs entre tous les serveurs du membre"""
        if self.get_account(user, "SYS")["sync"] or force:
            base = self.data[user.server.id]["USERS"][user.id].get(to_sync, False)
            if base:
                for serv in self.data:
                    if user.id in self.data[serv]["USERS"] and serv != user.server.id:
                        if self.data[serv]["USERS"][user.id]["SYS"]["sync"]:
                            if not sub_sync:
                                self.data[serv]["USERS"][user.id][to_sync] = base
                            else:
                                base = self.data[user.server.id]["USERS"][user.id][to_sync].get(sub_sync, False)
                                if base:
                                    self.data[serv]["USERS"][user.id][to_sync][sub_sync] = base
                self.save()
                return True
        return False

    def namelist(self, user: discord.Member, debug_reverse: bool = False):
        """Renvoie une liste des anciens pseudos & surnoms d'un membre"""
        server = user.server
        if debug_reverse:
            for s in self.past_nicknames:
                for u in self.past_nicknames[s]:
                    self.past_nicknames[s][u].reverse()
            dataIO.save_json("data/mod/past_nicknames.json", self.past_nicknames)
            for u in self.past_names:
                self.past_names[u].reverse()
            dataIO.save_json("data/mod/past_names.json", self.past_names)
            return True
        names = self.past_names[user.id] if user.id in self.past_names else None
        if user.id in self.past_nicknames[server.id]:
            nicks = self.past_nicknames[server.id][user.id]
            nicks = [escape_mass_mentions(nick) for nick in nicks]
        else:
            nicks = "Aucun"
        if names:
            names = [escape_mass_mentions(name) for name in names]
        else:
            names = "Aucun"
        return names, nicks

    def reset_past_names(self, user: discord.Member):
        """Reset l'historique des pseudos et surnoms d'un membre

        - Non synchronisé"""
        server = user.server
        try:
            self.past_names[user.id] = []
            dataIO.save_json("data/mod/past_names.json", self.past_names)
        except FileNotFoundError:
            pass
        try:
            self.past_nicknames[server.id][user.id] = []
            dataIO.save_json("data/mod/past_nicknames.json", self.past_nicknames)
        except FileNotFoundError:
            pass
        return True

    def reset_logs(self, user: discord.Member):
        """Reset les logs d'un membre sur le serveur

        - Non synchronisé"""
        u = self.get_account(user)
        u["LOGS"] = []
        self.save()
        return True

    def get_all_cache_games(self):
        """Retourne une liste de tous les jeux mis en cache"""
        total = []
        for s in self.data:
            data = self.data[s]["USERS"]
            for user in data:
                for g in data[user]["SYS"]["_cache_games"]:
                    if g not in total:
                        total.append(g)
        return total

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

    def sum_network_data(self, user: discord.Member):
        """Renvoie un Namedtuple qui résume les données Network du membre & du serveur

        -- Similaire au 'pay.sum_pay_data' du module Pay"""
        u = self.get_account(user)
        SumNetwork = namedtuple('SumNetwork', ['user', 'server', 'total_msg', 'join_count', 'quit_count', 'ban_count',
                                               'couleur', 'image_url'])
        return SumNetwork(user, user.server, u["STATS"]["msg_total"], u["STATS"]["join"], u["STATS"]["quit"],
                          u["STATS"]["ban"], u["SOCIAL"]["color"],  u["SOCIAL"]["image"])

    def get_greffons(self, user: discord.Member):
        """Retourne les paramètres des embeds dans une liste"""
        server = user.server
        pay = self.bot.get_cog("Pay").pay
        if pay.get_account(user):
            bank = pay.sum_pay_data(user)
        else:
            bank = None
        net = self.sum_network_data(user)
        # TODO: Ajouter plus d'add-ons en champs (Network, Karma, Assistant...)
        soc = self.get_account(user, "SOCIAL")
        l = []
        if soc["plus"]:
            for i in soc["plus"]:
                try:
                    form = soc["plus"][i].format(me=user, server=server, pay=bank, network=net)
                    l.append([i, form])
                except AttributeError as e:
                    l.append([i, "Ce greffon comporte une anomalie : {}".format(e)])
            return l
        return []

    async def display_card(self, user: discord.Member, mini: bool = False, brut: bool = False):
        """Affiche le profil d'un membre"""
        today = time.strftime("%d/%m/%Y", time.localtime())
        soc = self.get_account(user, "SOCIAL")
        titlename = user.name if user.display_name == user.name else "{} «{}»".format(user.name, user.display_name)
        desc = soc["bio"] if soc["bio"] else ""
        colorset = soc["color"] if soc["color"] else user.color
        crea_date, crea_jours = user.created_at.strftime("%d/%m/%Y"), (datetime.now() - user.created_at).days
        ariv_date, ariv_jours = user.joined_at.strftime("%d/%m/%Y"), (datetime.now() - user.joined_at).days
        old_ts = datetime.fromtimestamp(self.get_account(user, "OLDEST"))
        old_date, old_jours = old_ts.strftime("%d/%m/%Y"), (datetime.now() - old_ts).days
        flammes = self.get_account(user, "STATS")["flammes"]
        val = "**Création** — {} · **{}**j\n".format(crea_date, crea_jours)
        val += "**Arrivée** — {} · **{}**j\n".format(ariv_date, ariv_jours)
        val += "**1ère trace** — {} · **{}**j\n".format(old_date, old_jours)
        val += "\🔥{} — {}".format(len(flammes), flammes[-1]) if flammes else "\🔥0 — {}".format(today)
        vtxt = "\n‣ Connecté sur {}".format(user.voice.voice_channel.name) if user.voice.voice_channel else ""
        if not mini:
            logs = self.get_account(user, "LOGS")[-3:]
            logs.reverse()
            hist = "• **Actions :**\n" + "\n".join(["**{}** · {}".format(e[0] if e[1] == today else e[1], e[2])
                                                    for e in logs]) if logs else "• **Actions :** aucune\n"
            psd, srn = self.namelist(user)
            if type(psd) is list: psd.reverse() ; psd = ", ".join(psd[-3:])
            if type(srn) is list: srn.reverse() ; srn = ", ".join(srn[-3:])
            psetxt = "• **Pseudos** — {}\n• **Surnoms** — {}\n".format(psd if psd else "Aucun", srn if srn else "Aucun")
            em = discord.Embed(title=titlename, description=desc, color=colorset)
            em.set_thumbnail(url=user.avatar_url)
            em.add_field(name="Infos", value=val)
            roles = ", ".join(["*{}*".format(r.name) for r in user.roles if r.name != "@everyone"])
            em.add_field(name="Rôles & Présence", value=roles if roles else "Aucun" + vtxt)
            em.add_field(name="Historique", value=psetxt + hist)
            if soc["image"]:
                em.set_image(url=soc["image"])
            embs = self.get_greffons(user)
            if embs:
                for i in embs:
                    em.add_field(name=i[0], value=i[1])
        else:
            psd, srn = self.namelist(user)
            if type(psd) is list: psd.reverse() ; psd = ", ".join(psd[-3:])
            if type(srn) is list: srn.reverse() ; srn = ", ".join(srn[-3:])
            psetxt = "\n\n• **Pseudos** — {}\n• **Surnoms** — {}".format(psd if psd else "Aucun",
                                                                         srn if srn else "Aucun")
            em = discord.Embed(color=colorset)
            em.set_author(name=titlename, icon_url=user.avatar_url)
            em.add_field(name="Infos", value=val)
            roles = ", ".join(["*{}*".format(r.name) for r in user.roles if r.name != "@everyone"])
            em.add_field(name="Rôles", value=roles if roles else "Aucun")
            em.add_field(name="Changements", value=psetxt)
        rx = " | {}".format(user.game.name) if user.game else ""
        em.set_footer(text="ID — {}{}".format(user.id, rx), icon_url=self.get_status_img(user))
        if brut:
            return em
        await self.bot.say(embed=em)


class Network:
    """Iota Network - Statistiques & fonctionnalités sociales"""
    def __init__(self, bot):
        self.bot = bot
        self.app = NetworkApp(bot, "data/network/data.json")

    @commands.group(no_pm=True, pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def netsys(self, ctx):
        """Paramètres locaux de Iota Network"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @netsys.command(name="checkpay", pass_context=True)
    async def _pay_verify(self, ctx):
        """Vérifie que le système Iota Pay est connecté à Network"""
        pay = self.bot.get_cog("Pay").pay
        try:
            pay.api_pong()
        except:
            await self.bot.say("**Erreur** ─ L'API Pay ne répond pas")
            return
        await self.bot.say("**Connectée** ─ L'API Pay répond correctement")

    @netsys.command(pass_context=True)
    async def forcesave(self, ctx):
        """Force l'API Network à sauvegarder les données"""
        self.app.save(force=True)
        await self.bot.say("**Sauvegarde effectuée avec succès**")

    @netsys.command(pass_context=True, hidden=True)
    async def resetall(self, ctx):
        """Reset les données de Network"""
        self.app.reset()
        await self.bot.say("**Reset effectué avec succès**")

    @netsys.command(pass_context=True)
    async def resetuser(self, ctx, user: discord.Member, sub: str = None):
        """Reset un membre entièrement ou partiellement"""
        if sub:
            if sub.upper() == "LOGS":
                self.app.reset_logs(user)
                await self.bot.say("**Succès** ─ Les logs ont été reset avec succès (sur ce serveur seulement)")
            elif sub.upper() == "NAMES":
                self.app.reset_past_names(user)
                await self.bot.say("**Succès** ─ Les anciens pseudos et surnoms ont été reset avec succès "
                                   "(sur ce serveur seulement)")
            else:
                await self.bot.say("**Inconnu** ─ Cette subclasse n'existe pas.")
        else:
            self.app.get_account(user, reset=True)
            await self.bot.say("**Succès** ─ Ce membre a été reset")

    @netsys.command(pass_context=True, hidden=True)
    async def namesinv(self, ctx):
        """Inverse le fichier de noms et surnoms pour régler un probleme récurrent..."""
        if self.app.namelist(ctx.message.author, debug_reverse=True):
            await self.bot.say("**Succès** - Les données ont été inversées")
        else:
            await self.bot.say("**Erreur** - Impossible d'inverser les valeurs")

    @netsys.command(pass_context=True, hidden=True)
    async def miniemoji(self, ctx, emoji: str = None):
        """Change l'Emoji faisant apparaitre une version 'mini' de la carte du membre visé

        Par défaut = 👤"""
        defaut = "👤"
        data = self.app.get_server_raw_data(ctx.message.server, "SYS")
        if emoji:
            data["minicard_emoji"] = emoji
            await self.bot.say("**Succès** — La mini-carte s'affichera en réagissant à un message avec {}"
                               "".format(emoji[1:]))
        else:
            data["minicard_emoji"] = defaut
            await self.bot.say("**Reset** — L'emoji de base {} à été restauré".format(defaut))
        self.app.save()

    @commands.group(name="carte", aliases=["c", "card"], pass_context=True, invoke_without_command=True, no_pm=True)
    async def _carte(self, ctx, membre: discord.Member = None):
        """Carte de membre Iota Network et commandes associées

        - En absence de mention, renvoie la carte du membre invocateur"""
        if ctx.invoked_subcommand is None:
            if not membre:
                membre = ctx.message.author
            await ctx.invoke(self.display, membre=membre)

    @_carte.command(pass_context=True)
    async def display(self, ctx, membre: discord.Member = None):
        """Affiche la carte Iota Network du membre"""
        membre = membre if membre else ctx.message.author
        if self.app.get_account(membre):
            await self.app.display_card(membre)
        else:
            await self.bot.say("**Erreur** — Vous n'avez pas de compte Network")

    @_carte.command(pass_context=True)
    async def sync(self, ctx):
        """Active/Désactive la synchonisation de la carte avec les autres serveurs

        Sens: ICI >>> sync >>> Autres serveurs"""
        u = self.app.get_account(ctx.message.author, "SYS")
        if u["sync"]:
            u["sync"] = False
            await self.bot.say("**Synchronisation désactivée** — "
                               "Votre carte sur ce serveur sera indépendante des autres serveurs")
        else:
            u["sync"] = True
            await self.bot.say("**Synchronisation activée** — "
                               "Votre carte sera synchronisée avec les autres serveurs l'autorisant")
            self.app.sync_account(ctx.message.author, "SOCIAL", force=True)
        self.app.save()

    @_carte.command(pass_context=True)
    async def bio(self, ctx, *texte):
        """Modifie la bio de sa carte Network"""
        u = self.app.get_account(ctx.message.author, "SOCIAL")
        if texte:
            u["bio"] = " ".join(texte)
            await self.bot.say("**Bio ajoutée** — Votre bio s'affichera en haut de votre carte")
        else:
            await self.bot.say("**Bio supprimée** — Votre bio n'affichera aucun texte")
            u["bio"] = None
        self.app.sync_account(ctx.message.author, "SOCIAL")
        self.app.add_log(ctx.message.author, "Changement de bio", True)
        self.app.save()

    @_carte.command(pass_context=True)
    async def image(self, ctx, url: str = None):
        """Modifier sa vitrine

        Ne supporte que des URL, ne pas en mettre retire l'image de votre carte"""
        u = self.app.get_account(ctx.message.author, "SOCIAL")
        if url:
            if url.endswith("gif") or url.endswith("png") or url.endswith("jpg") or url.endswith("jpeg"):
                if u["image"]:
                    await self.bot.say("**Image modifiée** — Elle s'affichera en bas de votre carte")
                else:
                    await self.bot.say("**Image ajoutée** — Elle s'affichera en bas de votre carte")
                u["image"] = url
                self.app.sync_account(ctx.message.author, "SOCIAL")
                self.app.add_log(ctx.message.author, "Changement de vitrine")
                self.app.save()
            else:
                await self.bot.say("**Image inatteignable** — Fournissez s'il-vous-plaît un lien direct vers l'image "
                                   "(png, jpg, jpeg ou gif)")
        else:
            await self.bot.say("**Image retirée** — Elle se n'affichera plus sur votre carte")

    @_carte.command(pass_context=True)
    async def couleur(self, ctx, couleur_hex: str = None):
        """Changer la couleur du bord gauche de sa carte

        Ne pas mettre de couleur affichera la couleur de votre pseudo sur le serveur"""
        u = self.app.get_account(ctx.message.author, "SOCIAL")
        col = couleur_hex
        if col:
            if "#" in col:
                col = col[1:]
            elif "0x" in col:
                col = col[2:]
            if col == "000000":
                await self.bot.say("**Info** — #000000 est considéré comme la valeur par défaut par Discord et ne "
                                   "s'affichera donc pas sur votre carte même si la démonstration fonctionne.\n"
                                   "Si vous voulez du noir, utilisez #000001.")
            if len(col) == 6:
                col = int(col, 16)
                u["color"] = col
                em = discord.Embed(color= u["color"],
                                   description="**Succès** — Voici une démonstration de la couleur choisie")
                em.set_footer(text="Besoin d'aide ? Allez sur http://www.color-hex.com/")
                await self.bot.say(embed=em)
                self.app.sync_account(ctx.message.author, "SOCIAL")
                self.app.add_log(ctx.message.author, "Changement de couleur de barre")
                self.app.save()
                return
            await self.bot.say("**Oups...** — On dirait que ce n'est pas de l'hexadécimal ! "
                               "Aidez-vous avec http://www.color-hex.com/")
        else:
            u["color"] = None
            self.app.sync_account(ctx.message.author, "SOCIAL")
            self.app.add_log(ctx.message.author, "Suppression de la couleur de barre")
            self.app.save()
            await self.bot.say("**Couleur retirée** — La couleur affichée sera donc toujours celle de votre pseudo")


    @_carte.group(aliases=["g"], no_pm=True, pass_context=True)
    async def greffon(self, ctx):
        """Gestion des greffons de votre carte"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @greffon.command(name="add", pass_context=True)
    async def _add(self, ctx, titre: str, *contenu: str):
        """Ajouter un greffon à sa carte

        titre - Nom du greffon s'affichant au haut de celui-ci (N'oubliez pas les guillemets pour des noms composés)
        contenu - Contenu du greffon, pouvant être formatté de différentes manières grâce aux intégrations (Voir Wiki)
        -- Limité à 3 greffons par membre"""
        user = ctx.message.author
        u = self.app.get_account(user)
        greffons = self.app.get_greffons(user)
        colorset = u["SOCIAL"]["color"] if u["SOCIAL"]["color"] else user.color
        if len(greffons) <= 3:
            contenu = " ".join(contenu)
            if 2 <= len(titre) <= 32 and 2 <= len(contenu) <= 256:
                if titre not in [g[0] for g in greffons]:
                    contenu = contenu.replace("\\n", "\n")
                    contenu = contenu.replace("§", "\n")
                    u["SOCIAL"]["plus"][titre] = contenu
                    em = discord.Embed(colour=colorset, title=titre, description=contenu)
                    em.set_footer(text="Faîtes '{}carte' pour voir le greffon dans votre carte".format(ctx.prefix))
                    self.app.add_log(user, "A ajouté un greffon nommé *{}*".format(titre))
                    await self.bot.say("**Greffon ajouté** — Voici une démonstration de votre greffon", embed=em)
                    self.app.save()
                else:
                    await self.bot.say("**Doublon** — Un greffon sous ce nom existe déjà")
            else:
                await self.bot.say("**Limites** — Vous devez suivre ces limites:\n"
                                   "• Le `titre` doit avoir entre 2 et 32 caractères\n"
                                   "• Le `contenu` doit avoir entre 2 et 256 caractères")
        else:
            await self.bot.say("**Pleine** — Votre carte est pleine, vous n'avez le droit qu'à 3 greffons à la fois")

    @greffon.command(name="del", pass_context=True)
    async def _del(self, ctx, titre: str = None):
        """Retirer un greffon de sa carte

        Si aucun titre n'est spécifié, renvoie la liste"""
        user = ctx.message.author
        u = self.app.get_account(user)
        greffons = self.app.get_greffons(user)
        if greffons:
            if not titre:
                txt = ""
                for g in greffons:
                    txt += "• **{}** — {}\n\n".format(g[0], g[1])
                em = discord.Embed(title="Vos greffons", description=txt, colour=user.color)
                em.set_footer(text="Faîtes '{}c g del' suivie du nom pour supprimer le greffon".format(ctx.prefix))
                await self.bot.say(embed=em)
            elif titre.lower() in [g[0].lower() for g in greffons]:
                for g in u["SOCIAL"]["plus"]:
                    if g.lower() == titre.lower():
                        del u["SOCIAL"]["plus"][g]
                        self.app.sync_account(user, "SOCIAL")
                        self.app.add_log(user, "A retiré un greffon nommé *{}*".format(titre))
                        await self.bot.say("**Greffon supprimé** — Il n'apparaitra plus sur votre carte")
                        self.app.save()
                        return
                await self.bot.say("**Erreur** — Je n'ai pas réussi à retirer ce greffon")
            else:
                await self.bot.say("**Introuvable** — Ce greffon ne semble pas exister.\n"
                                   "Vous avez pensé à mettre des guillemets si le titre est composé de plus d'un mot ?")
        else:
            await self.bot.say("**Aucun greffon** — Vous n'avez aucun greffon à supprimer")

    @greffon.command(name="liste", pass_context=True)
    async def _list(self, ctx, titre: str = None):
        """Renvoie la liste des greffons de sa carte

        Si un titre est donné, renvoie aussi la commande lié au greffon"""
        user = ctx.message.author
        greffons = self.app.get_greffons(user)
        if titre and greffons:
            greffon = [g for g in greffons if g[0].lower() == titre.lower()][0]
            if greffon:
                name = greffon[0]
                greffon = self.app.get_account(user, "SOCIAL")["plus"][name]
                cmd = "\n\n**Commande** — `{}c g add \"{}\" \"{}\"`".format(ctx.prefix, name,
                                                                            greffon.replace("\n", "§"))
                em = discord.Embed(titre="Greffon \"{}\"".format(greffon[0]), description=greffon[1] + cmd,
                                   colour=user.color)
                await self.bot.say(embed=em)
            else:
                await self.bot.say("**Introuvable** — Ce greffon ne semble pas exister.\n"
                                   "Vous avez pensé à mettre des guillemets si le titre est composé de plus d'un mot ?")
        elif greffons:
            txt = ""
            for g in greffons:
                txt += "• **{}** — {}\n\n".format(g[0], g[1])
            em = discord.Embed(title="Vos greffons", description=txt, colour=user.color)
            await self.bot.say(embed=em)
        else:
            await self.bot.say("**Aucun greffon** — Vous n'avez aucun greffon sur votre carte")

    @commands.command(aliases=["ns"], pass_context=True)
    async def stats(self, ctx, user: discord.Member = None):
        """Affiche ses statistiques Network (ou celles du membre visé)"""
        user = user if user else ctx.message.author
        u = self.app.get_account(user, "STATS")
        em = discord.Embed(title="Statistiques — {}".format(user.name), color=user.color)
        txt = "**Ratio msg/j** — {}"

    @commands.group(aliases=["apps"], no_pm=True, pass_context=True)
    async def jeux(self, ctx):
        """Gestion de vos jeux & applications enregistrés"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    # TODO: Faire toutes ces commandes lorsque un nombre important de jeux seront détectés
    @jeux.command(pass_context=True)
    async def add(self, ctx, *nom: str):
        """Ajoute un jeu/application à votre collection parmi celles et ceux enregistrés"""
        await self.bot.say("**Bientôt disponible** — Ce système a besoin d'analyser dans un premier temps les jeux "
                           "qui sont joués par les membres afin d'apprendre à différentier les vrais jeux des status "
                           "qui ont été personnalisés.")

    @jeux.command(aliases=["del"], pass_context=True)
    async def delete(self, ctx, *nom: str):
        """Retire un jeu/application à votre collection parmi celles et ceux possédés"""
        await self.bot.say("**Bientôt disponible** — Ce système a besoin d'analyser dans un premier temps les jeux "
                           "qui sont joués par les membres afin d'apprendre à différentier les vrais jeux des status "
                           "qui ont été personnalisés.")

    @jeux.command(pass_context=True)
    async def list(self, ctx, *nom: str):
        """Liste les jeux que vous avez sauvegardés sur votre profil"""
        await self.bot.say("**Bientôt disponible** — Ce système a besoin d'analyser dans un premier temps les jeux "
                           "qui sont joués par les membres afin d'apprendre à différentier les vrais jeux des status "
                           "qui ont été personnalisés.")

    # ======== TRIGGERS ==========
    async def network_msgadd(self, message):
        """Détection des nouveaux messages"""
        if hasattr(message, "server"):
            if self.app.get_account(message.author):
                date, hier = datetime.now().strftime("%d/%m/%Y"), (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
                author, server = message.author, message.server
                p = self.app.get_account(author)
                p["STATS"]["msg_total"] += 1

                if hier in p["STATS"]["flammes"]:
                    if date not in p["STATS"]["flammes"]:
                        p["STATS"]["flammes"].append(date)
                elif date not in p["STATS"]["flammes"]:
                    p["STATS"]["flammes"] = [date]

                if ":" in message.content:
                    output = re.compile(':(.*?):', re.DOTALL | re.IGNORECASE).findall(message.content)
                    if output:
                        for i in output:
                            if i in [e.name for e in server.emojis]:
                                p["STATS"]["emojis"][i] = p["STATS"]["emojis"][i] + 1 if i in p["STATS"]["emojis"] else 1
                self.app.save()

    async def network_msgdel(self, message):
        """Détection des suppressions de messages"""
        if not hasattr(message, "server"):
            return
        if hasattr(message, "server") and self.app.get_account(message.author):
            author = message.author
            p = self.app.get_account(author)
            p["STATS"]["msg_suppr"] += 1
            self.app.save()

    async def network_react(self, reaction, author):
        """Détection des réactions"""
        if not hasattr(author, "server"):
            return
        message = reaction.message
        if hasattr(message, "server") and self.app.get_account(author):
            miniemote = self.app.get_server_raw_data(message.server, "SYS")
            miniemote = miniemote["minicard_emoji"]
            if type(reaction.emoji) == str:
                if reaction.emoji == miniemote:
                    await self.bot.send_message(author,
                                                embed=await self.app.display_card(message.author, True, True))

            server = message.server
            p = self.app.get_account(author)
            if type(reaction.emoji) == str:
                name = reaction.emoji
            else:
                name = reaction.emoji.name
            if name in [e.name for e in server.emojis]:
                p["STATS"]["emojis"][name] = p["STATS"]["emojis"][name] + 1 if name in p["STATS"]["emojis"] else 1
            self.app.save()

    async def network_join(self, user: discord.Member):
        """Détection des arrivées sur le serveur"""
        if not hasattr(user, "server"):
            return
        p = self.app.get_account(user, "STATS")
        p["join"] += 1
        if p["quit"] > 0:
            self.app.add_log(user, "Retour sur le serveur")
        else:
            self.app.add_log(user, "Arrivée sur le serveur")
        self.app.save()

    async def network_quit(self, user: discord.Member):
        """Détection des départs du serveur"""
        if not hasattr(user, "server"):
            return
        p = self.app.get_account(user)
        p["STATS"]["quit"] += 1
        roles = [r.id for r in user.roles if r.name != "@everyone"]
        if roles:
            p["SYS"]["save_roles"] = roles
        self.app.add_log(user, "Quitte le serveur")
        self.app.save()

    async def network_ban(self, user):
        """Détection des bans"""
        if not hasattr(user, "server"):
            return
        p = self.app.get_account(user)
        p["STATS"]["ban"] += 1
        self.app.add_log(user, "Banni du serveur")
        self.app.save()

    async def network_perso(self, before, after):
        """Détection des changements sur un profil d'un membre"""
        if not hasattr(after, "server"):
            return
        p = self.app.get_account(after)
        if after.name != before.name:
            self.app.add_log(after, "Changement de pseudo pour *{}*".format(after.name))
        if after.display_name != before.display_name:
            if after.display_name == after.name:
                self.app.add_log(after, "Surnom retiré")
            else:
                self.app.add_log(after, "Changement du surnom pour *{}*".format(after.display_name))
        if after.avatar_url != before.avatar_url:
            url = before.avatar_url
            url = url.split("?")[0]  # On retire le reformatage serveur Discord
            self.app.add_log(after, "Changement d'avatar [(?)]({})".format(url))
        if after.top_role != before.top_role:
            if after.top_role > before.top_role:
                self.app.add_log(after, "A reçu le rôle *{}*".format(after.top_role.name))
            else:
                if after.top_role.name != "@everyone":
                    self.app.add_log(after, "A perdu le rôle *{}*".format(before.top_role.name))
                else:
                    self.app.add_log(after, "Ne possède plus de rôles")
        p = p["SYS"]["_cache_games"]
        genp = self.app.get_all_cache_games()
        if after.game:
            if after.game.name:
                if after.game.name.lower() not in [g.lower() for g in genp]:
                    p.append(after.game.name)
        self.app.save()


def check_folders():
    if not os.path.exists("data/network"):
        print("Création du dossier NETWORK...")
        os.makedirs("data/network")


def check_files():
    if not os.path.isfile("data/network/data.json"):
        print("Création de Network/data.json")
        dataIO.save_json("data/network/data.json", {})


def setup(bot):
    check_folders()
    check_files()
    n = Network(bot)
    bot.add_listener(n.network_msgadd, "on_message")
    bot.add_listener(n.network_msgdel, "on_message_delete")
    bot.add_listener(n.network_react, "on_reaction_add")
    bot.add_listener(n.network_join, "on_member_join")
    bot.add_listener(n.network_quit, "on_member_remove")
    bot.add_listener(n.network_perso, "on_member_update")
    bot.add_listener(n.network_ban, "on_member_ban")
    bot.add_cog(n)
