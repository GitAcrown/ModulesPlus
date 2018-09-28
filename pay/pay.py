import asyncio
from datetime import datetime, timedelta
import operator
import os
import random
import string
import time
from collections import namedtuple

import discord
from __main__ import send_cmd_help
from discord.ext import commands

from .utils import checks
from .utils.dataIO import fileIO, dataIO

# Ce module est volontairement "sur-commenté" dans un soucis de lisibilité et afin que certaines personnes puisse
# s'en servir de base

class PayAPI:
    """API Iota Pay | Système de monnaie globale par serveur"""
    def __init__(self, bot, path):
        self.bot = bot
        self.data = dataIO.load_json(path)
        self.backup_capital = dataIO.load_json("data/capital/data.json")
        self.sys_defaut = {"MONNAIE": {"SINGULIER": "crédit", "PLURIEL": "crédits", "SYMBOLE": "cds"}}
        self.default = {"USERS": {}, "SYSTEM": self.sys_defaut}
        self.cooldown = {}

    def _save(self):
        fileIO("data/pay/data.json", "save", self.data)
        return True

    def api_pong(self):
        """Renvoie un pong signifiant que l'API est connectée"""
        return True

    def backup_capitalAPI(self, server: discord.Server):
        """Backup les données de l'ancien module Capital"""
        if server.id in self.backup_capital:
            backup = self.backup_capital[server.id]
            for user in backup["USERS"]:
                backup["USERS"][user]["SOLDE"] = round(backup["USERS"][user]["SOLDE"] / 2)
                backup["USERS"][user]["TRSAC"] = []
                del backup["USERS"][user]["EXTRA"]
                backup["USERS"][user]["PLUS"] = {}
                backup["USERS"][user]["OPEN"] = True
            mon = backup["SYSTEM"]["MONNAIE"]
            backup["SYSTEM"] = {"MONNAIE": {"SINGULIER": mon["SINGULIER"], "PLURIEL": mon["PLURIEL"],
                                            "SYMBOLE": mon["SYMBOLE"]}}
            self.data[server.id] = backup
            self._save()
            return True
        else:
            return False
    
    # SERVEUR ------------------------
    def _get_server_raw_data(self, server: discord.Server):
        """Renvoie les données du serveur en brut

        >> création si absence"""
        if server.id not in self.data:
            self.data[server.id] = self.default
            self._save()
        return self.data[server.id]

    # COMPTES ------------------------
    def new_account(self, user: discord.Member):
        """Créer un nouveau compte sur le serveur"""
        server = user.server
        data = self._get_server_raw_data(server)["USERS"]
        if user.id not in data:
            data[user.id] = {"SOLDE": 100,
                             "OPEN": True,
                             "TRSAC": [],
                             "CREE": datetime.now().strftime("%d/%m/%Y à %H:%M"),
                             "PLUS": {}}
            self._save()
            return self._account_obj(user)
        return False

    def _account_obj(self, user: discord.Member):
        """Renvoie un objet Account() contenant les informations bancaires du membre"""
        server = user.server
        data = self._get_server_raw_data(server)["USERS"][user.id]
        Account = namedtuple('Account', ['user','solde', 'historique', 'creation', 'open'])
        return Account(user, data["SOLDE"], data["TRSAC"], data["CREE"], data["OPEN"])

    def get_account(self, user: discord.Member, w: bool = False, m: bool = False, ignore_close: bool = False):
        """Renvoie le compte Iota Pay du membre

        -w : 'Write', renvoie les données en brut
        -m : 'Make', créé un compte si le membre n'en a pas"""
        server = user.server
        data = self._get_server_raw_data(server)["USERS"]
        if user.id not in data:
            if m:  # make
                return self.new_account(user)
            return False
        if w:  # write
            if data[user.id]["OPEN"] or ignore_close:
                return data[user.id]
            return False  # Dans le doute
        if data[user.id]["OPEN"] or ignore_close:
            return self._account_obj(user)
        return False

    def sum_pay_data(self, user: discord.Member):
        """Renvoie un pack d'informations essentielles sur le membre et son serveur

        Utile pour obtenir un maximum d'information dans un unique Namedtuple"""
        pay = self.get_account(user, ignore_close=True)
        serv = self.get_server_sys(user.server)
        m_auto = self.get_money_name(user.server, pay.solde)
        open = "Valide" if pay.open else "Suspendu"
        total = self.total_server_credits(user.server)
        Essential = namedtuple('Essential', ['user', 'server', 'solde', 'monnaie', 'monnaie_auto', 'valide',
                                             'timestamp', 'server_total'])
        return Essential(user, user.server, pay.solde, serv.monnaie, m_auto, open, pay.creation, total)

    def get_all_accounts(self, server: discord.Server = None):
        """Renvoie une liste de tous les comptes de membre"""
        liste = []
        if not server:
            for serv in self.data:
                server = self.bot.get_server(serv)
                for member in server.members:
                    if self.get_account(member):
                        liste.append(self.get_account(member))
        else:
            for member in server.members:
                if self.get_account(member):
                    liste.append(self.get_account(member))
        return liste

    def account_migration(self, source: discord.Member, destinataire: discord.Member):
        """Effectue une migration de compte entre deux membres"""
        server = source.server
        if source.id in self.data[server.id]["USERS"]:
            compte = self.data[server.id]["USERS"][source.id]
            self.data[server.id]["USERS"][destinataire.id] = compte
            del self.data[server.id]["USERS"][source.id]
            self._save()
            return True
        return False

    async def sign_up(self, ctx, user: discord.Member = None):
        """Inscrit un membre sur le système bancaire du serveur"""
        user = user if user else ctx.message.author
        msg = await self.bot.say("**Tu n'as pas de compte Pay** ─ Veux-tu en ouvrir un ?")
        await self.bot.add_reaction(msg, "✔")
        await self.bot.add_reaction(msg, "✖")
        await self.bot.add_reaction(msg, "❔")
        await asyncio.sleep(0.1)
        def check(reaction, user):
            return not user.bot

        rep = await self.bot.wait_for_reaction(["✔", "✖", "❔"], message=msg, timeout=30, check=check,
                                               user=user)
        if rep is None or rep.reaction.emoji == "✖":
            await self.bot.delete_message(msg)
            await self.bot.say("**Annulé** ─ Tu pourra toujours en créer un avec `{}pay new`".format(ctx.prefix))
            return False
        elif rep.reaction.emoji == "✔":
            if self.new_account(user):
                await self.bot.delete_message(msg)
                await self.bot.say("**Ouvert** ─ Ton compte a été ouvert avec succès {} !".format(
                    user.name))
                return True
            else:
                await self.bot.delete_message(msg)
                await self.bot.say("**Erreur** ─ Impossible de créer ton compte {} !\nLe serveur est peut-être sur "
                                   "Blacklist.".format(user.name))
                return False
        elif rep.reaction.emoji == "❔":
            await self.bot.delete_message(msg)
            em = discord.Embed(color= user.color, title="Ouvrir un compte Iota Pay",
                               description= "Certaines fonctionnalités sur ce bot utilisent un système monétaire appelé"
                                            " *Iota Pay* permettant par exemple de pouvoir participer à divers jeux.\n"
                                            "Il est important de savoir que cette monnaie est **virtuelle** et ne "
                                            "pourra être échangée contre de l'argent réel.\n"
                                            "A la création du compte, aucune information ne te sera demandée.")
            em.set_footer(text="Veux-tu ouvrir un compte ?")
            info = await self.bot.say(embed=em)
            await self.bot.add_reaction(info, "✔")
            await self.bot.add_reaction(info, "✖")
            await asyncio.sleep(0.1)
            rep = await self.bot.wait_for_reaction(["✔", "✖"], message=info, timeout=20, check=check,
                                                   user=user)
            if rep is None or rep.reaction.emoji == "✖":
                await self.bot.delete_message(info)
                await self.bot.say("**Annulé** ─ Tu pourra toujours en créer un avec `{}pay new`".format(ctx.prefix))
                return False
            elif rep.reaction.emoji == "✔":
                if self.new_account(user):
                    await self.bot.delete_message(info)
                    await self.bot.say("**Ouvert** ─ Ton compte a été ouvert avec succès {} !".format(
                        user.name))
                    return True
                else:
                    await self.bot.delete_message(info)
                    await self.bot.say("**Erreur** ─ Impossible de créer ton compte {} !\nLe serveur est peut-être sur "
                                       "Blacklist.".format(user.name))
                    return False
        await self.bot.say("**Erreur** ─ Je n'ai pas compris ...")
        return False

    async def verify(self, ctx, user: discord.Member = None, ignore_close: bool=False):
        """Vérifie si le membre possède un compte et lui demande automatiquement sa création en cas de besoin"""
        user = user if user else ctx.message.author
        data = self.get_account(user=user, ignore_close=True)
        if data:
            if data.open or ignore_close:
                return True
            await self.bot.say("**Compte bloqué** ─ Il semblerait que ton compte soit bloqué. "
                               "Consulte un modérateur pour en savoir plus.")
            return False
        done = await self.sign_up(ctx)
        if done:
            return True
        return False

    # HISTORIQUE ------------------------
    def _transaction_obj(self, trans: list):
        """Renvoie un objet Transaction()"""
        server_id = user_id = None
        for server in self.data:
            for user in self.data[server]["USERS"]:
                if trans in self.data[server]["USERS"][user]["TRSAC"]:
                    server_id, user_id = server, user
        Transaction = namedtuple('Transaction', ['id', 'ts_heure', 'ts_jour', 'somme', 'desc', 'user_id', 'server_id',
                                                 'liens', 'type'])
        return Transaction(trans[0], trans[1], trans[2], trans[3], trans[4], user_id, server_id, trans[5], trans[6])
        # --Info             id       heure     jour      somme     desc      ----    ----    link       type

    def _obj_transaction(self, trans: list):  # Pour la compatibilité avec Capital
        return self._transaction_obj(trans)

    def id_to_transaction(self, trs_id: str, w: bool = False):
        """Retrouve la transaction liée à l'identifiant"""
        for serv in self.data:
            trs_list = []
            for user in self.data[serv]["USERS"]:
                for trs in self.data[serv]["USERS"][user]["TRSAC"]:
                    if trs[0] == trs_id:
                        return self._transaction_obj(trs) if not w else trs
        return False

    def ajt_transaction(self, user: discord.Member, type_t: str, somme: int, reason: str):
        """Ajoute une transaction à l'historique du membre"""
        user = self.get_account(user, True)
        if user:
            jour, heure = time.strftime("%d/%m/%Y", time.localtime()), time.strftime("%H:%M", time.localtime())
            clef = str(''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(4)))
            while self.id_to_transaction(clef):
                clef = str(
                    ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(4)))
            event = [clef, heure, jour, somme, reason, [], type_t]
            user['TRSAC'].append(event)
            if len(user["TRSAC"]) > 20:
                user["TRSAC"].remove(user["TRSAC"][0])
            return self._transaction_obj(event)
        return False

    def link_transactions(self, trans_a, trans_b):
        """Relie deux transactions entre elles"""
        a, b = self.id_to_transaction(trans_a, True), self.id_to_transaction(trans_b, True)
        if a and b:
            a[5].append(b[0]); b[5].append(a[0])
            self._save()
            return True
        return False

    def get_lasts_transactions(self, user: discord.Member, nb: int = 1):
        """Renvoie les dernières transactions du membre"""
        user = self.get_account(user, True, ignore_close=True)
        if user:
            if nb >= 1:
                h = user['TRSAC'][-nb:]
                return [self._transaction_obj(i) for i in h]
            else:
                return [self._transaction_obj(i) for i in user['TRSAC']]
        return False

    def get_day_transactions(self, user: discord.Member, jour: str = None):
        if not jour:
            jour = time.strftime("%d/%m/%Y", time.localtime())
        user = self.get_account(user, True)
        if user:
            liste = []
            for t in user['TRSAC']:
                if t[2] == jour:
                    j, h = t[2], t[1]
                    liste.append([time.mktime(time.strptime("{} {}".format(j, h), "%d/%m/%Y %H:%M")),
                                  self._obj_transaction(t)])
            sort = sorted(liste, key=operator.itemgetter(0), reverse=True)
            liste = [s[1] for s in sort]
            return liste
        return False

    def get_total_day_gain(self, user : discord.Member, jour: str = None):
        if self.get_day_transactions(user, jour):
            return sum([t.somme for t in self.get_day_transactions(user, jour)])
        return 0

    # TRANSACTIONS ------------------------
    def gain_credits(self, user: discord.Member, somme: int, raison: str):
        """Ajoute des crédits au membre"""
        data = self.get_account(user, True)
        if somme > 0:
            data["SOLDE"] += somme
            t = self.ajt_transaction(user, "GAIN", somme, raison)
            self._save()
            return t
        return False

    def gain_credits_prc(self, user: discord.Member, pourcent: int, raison: str):
        """Ajoute des crédits au membre par rapport à un pourcentage"""
        data = self.get_account(user, True)
        if 0 < pourcent <= 100:
            diff = data.solde * (pourcent / 100)
            return self.gain_credits(user, round(diff), raison)
        return False

    def depot_credits(self, user: discord.Member, somme: int, raison: str):  # Compatibilité Capital
        return self.gain_credits(user, somme, raison)

    def perte_credits(self, user: discord.Member, somme: int, raison: str, ignore_min: bool=False):
        """Retire des crédits au membre"""
        somme = abs(somme)  # On s'assure que 'somme' est positive
        data = self.get_account(user, True)
        if self.enough_credits(user, somme):
            data["SOLDE"] -= somme
            t = self.ajt_transaction(user, "PERTE", -somme, raison)
            self._save()
            return t
        elif ignore_min:
            somme = data["SOLDE"]
            data["SOLDE"] = 0
            t = self.ajt_transaction(user, "PERTE", -somme, raison)
            self._save()
            return t
        return False

    def perte_credits_prc(self, user: discord.Member, pourcent: int, raison: str):
        """Retire des crédits au membre par rapport à un pourcentage"""
        data = self.get_account(user, True)
        if 0 < pourcent <= 100:
            diff = data.solde * (pourcent / 100)
            return self.perte_credits(user, round(diff), raison)
        return False

    def set_credits(self, user: discord.Member, somme: int, raison: str):
        """Change la valeur du solde du membre"""
        data = self.get_account(user, True)
        if somme >= 0:
            data["SOLDE"] = somme
            t = self.ajt_transaction(user, "SET", somme, raison)
            self._save()
            return t
        return False

    def enough_credits(self, user: discord.Member, depense: int):
        """Vérifie que le membre peut dépenser cette somme"""
        data = self.get_account(user)
        if data:
            return True if data.solde - depense >= 0 else False
        return False

    def transfert_credits(self, donneur: discord.Member, receveur: discord.Member, somme: int, raison: str):
        """Transfère les crédits d'un membre à un autre"""
        if donneur != receveur:
            if somme > 0:
                if self.enough_credits(donneur, somme):
                    dvr = self.perte_credits(donneur, somme, raison)
                    rvd = self.gain_credits(receveur, somme, raison)
                    self.link_transactions(dvr.id, rvd.id)
                    return True
        return False

    # SERVEUR ------------------------
    def total_server_credits(self, server: discord.Server):
        """Retourne le nombre total de crédits se trouvant sur le serveur"""
        if server.id in self.data:
            return sum([u.solde for u in self.get_all_accounts(server)])
        return False

    def _system_obj(self, server: discord.Server):
        """Retourne l'objet Systeme() contenant les paramètres du serveur"""
        data = self._get_server_raw_data(server)["SYSTEM"]
        Monnaie = namedtuple('Monnaie', ['singulier', 'pluriel', 'symbole'])
        money = Monnaie(data["MONNAIE"]["SINGULIER"], data["MONNAIE"]["PLURIEL"], data["MONNAIE"]["SYMBOLE"])
        System = namedtuple('System', ['server', 'monnaie'])
        return System(server, money)

    def get_server_sys(self, server: discord.Server = False, w: bool = False):
        if not server:
            tot = []
            for s in self.data:
                server = self.bot.get_server(s)
                tot.append(self._system_obj(server) if not w else self.data[server.id]["SYSTEM"])
            return tot
        return self._system_obj(server) if not w else self.data[server.id]["SYSTEM"]

    def gen_palmares(self, server: discord.Server, nombre: int):
        """Génère un top des membres les plus riches du serveur"""
        if server.id in self.data:
            mb = [n.id for n in server.members]
            liste = [[self.data[server.id]["USERS"][u]["SOLDE"], u] for u in self.data[server.id]["USERS"] if u in mb]
            sort = sorted(liste, key=operator.itemgetter(0), reverse=True)
            return sort[:nombre]
        return False

    def get_money_name(self, server: discord.Server, somme: int = 0, symbole: bool = False):
        """Renvoie le nom de la monnaie en fonction du contexte"""
        data = self._get_server_raw_data(server)["SYSTEM"]
        if symbole:
            return data["MONNAIE"]["SYMBOLE"]
        if somme > 1:
            return data["MONNAIE"]["PLURIEL"]
        return data["MONNAIE"]["SINGULIER"]

    def get_money(self, server: discord.Server, nombre: int = 0, symbole: bool = False):  # Compatibilité Capital
        return self.get_money_name(server, nombre, symbole)

    # COOLDOWN ------------------------
    def add_cooldown(self, user: discord.Member, nom: str, duree: int):
        """Ajoute un cooldown à un membre

        -duree : en secondes"""
        server = user.server
        date = time.time() + duree
        if server.id in self.cooldown:
            if nom.lower() in self.cooldown[server.id]:
                if user.id in self.cooldown[server.id][nom.lower()]:
                    self.cooldown[server.id][nom.lower()][user.id] += duree
                else:
                    self.cooldown[server.id][nom.lower()][user.id] = date
            else:
                self.cooldown[server.id][nom.lower()] = {user.id : date}
        else:
            self.cooldown[server.id] = {nom.lower() : {user.id : date}}
        return self.cooldown[server.id][nom.lower()][user.id]

    def get_cooldown(self, user : discord.Member, nom: str):
        """Renvoie le cooldown - si il est nul, renvoie False

        -format_time : change le format du temps en output (j,h,m ou s)"""
        server = user.server
        now = time.time()
        if server.id not in self.cooldown:
            self.cooldown[server.id] = {}
            return False
        if nom.lower() not in self.cooldown[server.id]:
            return False
        if user.id in self.cooldown[server.id][nom.lower()]:
            if now <= self.cooldown[server.id][nom.lower()][user.id]:
                duree = int(self.cooldown[server.id][nom.lower()][user.id] - now)
                return self.auto_timeconvert(duree)
            else:
                del self.cooldown[server.id][nom.lower()][user.id]
                return False
        return False

    def is_cooldown_blocked(self, user: discord.Member, nom: str):  # Compatibilité Capital
        return self.get_cooldown(user, nom)

    # SYSTEME ------------------------
    def forcesave(self):
        """Force la sauvegarde de l'API"""
        return self._save()

    def reset_all_data(self, server: discord.Server = None):
        """Reset toutes les données d'un serveur (ou de tous les serveurs)"""
        if server:
            if server.id in self.data:
                self.data[server.id] = self.default
            else:
                return False
        else:
            self.data = {}
        self._save()
        return True

    def reset_user_data(self, user: discord.Member):
        """Reset toutes les données d'un membre"""
        server = user.server
        data = self._get_server_raw_data(server)["USERS"]
        if user.id in data:
            del data[user.id]
            self._save()
            return True
        return False

    # AUTRES -------------------------
    def auto_timeconvert(self, val: int):
        """Convertis automatiquement les secondes en unités plus pratiques

        > Objet TimeConv()"""
        j = h = m = 0
        while val >= 60:
            m += 1
            val -= 60
            if m == 60:
                h += 1
                m = 0
                if h == 24:
                    j += 1
                    h = 0
        txt = ""
        if j: txt += str(j) + "J "
        if h: txt += str(h) + "h "
        if m: txt += str(m) + "m "
        if val > 0: txt += str(val) + "s"
        TimeConv = namedtuple('TimeConv', ['jours', 'heures', 'minutes', 'secondes', 'string'])
        return TimeConv(j, h, m, val, txt)


class Pay:
    """Système monétaire virtuel et systèmes divers exploitant celle-ci"""
    def __init__(self, bot):
        self.bot = bot
        self.pay = PayAPI(bot, "data/pay/data.json")
        # Pour importer l'API : self.bot.get_cog("Pay").pay

    def check(self, reaction, user):
        return not user.bot

    @commands.group(name="bank", aliases=["b", "pay"], pass_context=True, invoke_without_command=True, no_pm=True)
    async def pay_account(self, ctx, membre: discord.Member = None):
        """Ensemble de commandes relatives au compte Iota Pay

        En absence de mention, renvoie les détails du compte de l'invocateur"""
        if ctx.invoked_subcommand is None:
            if not membre:
                membre = ctx.message.author
            await ctx.invoke(self.compte, user=membre)

    @pay_account.command(pass_context=True)
    async def new(self, ctx):
        """Ouvre un compte bancaire sur ce serveur"""
        data = self.pay.get_account(ctx.message.author)
        if data:
            await self.bot.say("**Tu as déjà un compte** ─ Consulte-le avec `{}pay`".format(ctx.prefix))
        else:
            await self.pay.sign_up(ctx)

    @pay_account.command(pass_context=True)
    async def compte(self, ctx, user: discord.Member = None):
        """Voir son compte Iota Pay sur ce serveur

        [user] - permet de voir le compte d'un autre membre"""
        user = user if user else ctx.message.author
        same = True if user == ctx.message.author else False
        data = self.pay.get_account(user, ignore_close=True)
        server = ctx.message.server
        if same or data:
            if await self.pay.verify(ctx, user, True):
                data = self.pay.get_account(user, ignore_close=True)
                blocktxt = " [Suspendu]" if not data.open else ""
                money, symb = self.pay.get_money_name(server, data.solde), self.pay.get_money_name(server, symbole=True)
                gains = self.pay.get_total_day_gain(user)
                gainstxt = "+{}".format(gains) if gains >= 0 else "{}".format(gains)
                em = discord.Embed(description="**Solde** ─ {0} {1}\n"
                                               "**Aujourd'hui** ─ {2} {3}".format(data.solde, money, gainstxt, symb),
                                   color=user.color)
                em.set_author(name=str(user) + blocktxt, icon_url=user.avatar_url)
                trs = self.pay.get_lasts_transactions(user, 3)
                trs.reverse()
                if trs:
                    txt = ""
                    for i in trs:
                        if i.type == "SET":
                            somme = "!{}".format(i.somme)
                        else:
                            somme = str(i.somme) if i.somme < 0 else "+{}".format(i.somme)
                        desc = i.desc if len(i.desc) <= 40 else i.desc[:40] + "..."
                        txt += "**{}** ─ *{}* `#{}`\n".format(somme, desc, i.id)
                    em.add_field(name="Historique", value=txt)
                em.set_footer(text="Iota Pay | {0}pay histo ─ Voir historique".format(ctx.prefix))
                await self.bot.say(embed=em)
            return
        else:
            await self.bot.say("**Compte introuvable** ─ Ce membre ne possède pas de compte Iota Pay valide")

    @pay_account.command(aliases=["histo"], pass_context=True)
    async def historique(self, ctx, user: discord.Member = None):
        """Affiche les 20 dernières transactions du membre"""
        user = user if user else ctx.message.author
        data = self.pay.get_account(user, ignore_close=True)
        server = ctx.message.server
        if data:
            jour = time.strftime("%d/%m/%Y", time.localtime())
            heure = time.strftime("%H:%M", time.localtime())
            txt = "*Consultez une transaction en détail avec* `{}pay show`\n\n".format(ctx.prefix)
            n = 1
            for t in self.pay.get_lasts_transactions(user, 0):
                temps = t.ts_jour
                if t.ts_jour == jour:
                    if t.ts_heure == heure:
                        temps = "À l'instant"
                    else:
                        temps = t.ts_heure
                txt += "{} | **{}** ─ *{}* `#{}`\n".format(temps, t.somme, t.desc, t.id)
                if len(txt) > 1980 * n:
                    em = discord.Embed(title="Historique de {}".format(user.name), description=txt, color= user.color)
                    em.set_footer(text="Iota Pay | Page {}".format(n))
                    await self.bot.say(embed=em)
                    txt = ""
                    n += 1

            em = discord.Embed(title="Historique de {}".format(user.name), description=txt, color=user.color)
            em.set_footer(text="Iota Pay | Page {}".format(n))
            await self.bot.say(embed=em)

    @pay_account.command(aliases=["trs"], pass_context=True)
    async def show(self, ctx, identifiant: str):
        """Affiche les détails d'une transaction"""
        if "#" in identifiant:
            identifiant = identifiant[1:]
        if len(identifiant) == 4:
            get = self.pay.id_to_transaction(trs_id=identifiant)
            if get:
                somme = str(get.somme) if get.somme < 0 else "+{}".format(get.somme)
                serveur = "Ici" if get.server_id == ctx.message.server.id else get.server_id
                txt = "*{}*\n\n**Type** ─ {}\n**Somme** ─ {}\n**Date** ─ Le {} à {}\n**Compte** ─ <@{}>\n" \
                      "**Serveur** ─ {}".format(get.desc, get.type, somme, get.ts_jour, get.ts_heure, get.user_id,
                                                serveur)
                em = discord.Embed(title="Transaction #{}".format(identifiant), description=txt, color=0xff4971)
                em.set_footer(text="Liées: {}".format(", ".join(get.liens) if get.liens else "aucune"))
                await self.bot.say(embed=em)
            else:
                await self.bot.say("**Introuvable** ─ Mauvais identifiant ou transaction expirée")
        else:
            await self.bot.say("**Erreur** ─ Identifiant invalide (composé de 4 lettres et/ou chiffres)")

    @commands.command(aliases=["don"], pass_context=True)
    async def give(self, ctx, user: discord.Member, somme: int, *raison):
        """Transférer de l'argent à un autre membre"""
        server = ctx.message.server
        raison = " ".join(raison) if raison else "Don de {} pour {}".format(ctx.message.author.name, user.name)
        if somme > 0:
            if self.pay.get_account(user):
                if await self.pay.verify(ctx):
                    if self.pay.enough_credits(ctx.message.author, somme):
                        cool = self.pay.get_cooldown(ctx.message.author, "give")
                        if not cool:
                            if self.pay.transfert_credits(ctx.message.author, user, somme, raison):
                                money = self.pay.get_money_name(server, symbole=True)
                                self.pay.add_cooldown(ctx.message.author, "give", 43200)  # Une demie journée
                                await self.bot.say("**Succès** ─ {} {} ont été transférés à *{}*".format(somme, money,
                                                                                                         user.name))
                            else:
                                await self.bot.say("**Erreur** ─ La transaction n'a pas été réalisée")
                        else:
                            await self.bot.say("**Cooldown** ─ Attendez encore {}".format(cool.string))
                    else:
                        await self.bot.say("**Impossible** ─ Tu n'as pas cette somme sur ton compte")
                else:
                    await self.bot.say("**Impossible** ─ Tu as besoin d'un compte *Pay* valide pour réaliser cette "
                                       "action")
            else:
                await self.bot.say("**Impossible** ─ Le membre visé n'a pas de compte bancaire valide")
        else:
            await self.bot.say("**Somme nulle ou négative** ─ Tu n'espérais pas lui voler de l'argent quand même ?!")

    @commands.command(aliases=["classement"], pass_context=True)
    async def palmares(self, ctx, nombre: int = 20):
        """Affiche un top des membres les plus riches du serveur"""
        server = ctx.message.server
        palm = self.pay.gen_palmares(server, nombre)
        uid = ctx.message.author.id
        n = 1
        symb = self.pay.get_money(server, symbole=True)
        txt = ""
        for l in palm:
            if len(txt) > 1980:
                await self.bot.say("**Trop grand** ─ Discord n'accepte pas des messages aussi longs, "
                                   "réduisez le nombre")
                return
            try:
                username = server.get_member(l[1]).name
            except:
                username = self.bot.get_user(l[1]).name
            if l[1] == uid:
                txt += "**{}.** __**{}**__ ─ {}{}\n".format(n, username, l[0], symb)
            else:
                txt += "**{}.** **{}** ─ {}{}\n".format(n, username, l[0], symb)
            n += 1
        em = discord.Embed(title="Palmares", description=txt, color=0xff4971)
        total = self.pay.total_server_credits(server)
        em.set_footer(text="Serveur {} | Total = {} {}".format(server.name, total,self.pay.get_money(server, total)))
        try:
            await self.bot.say(embed=em)
        except:
            await self.bot.say("**Erreur** ─ Le classement est trop long pour être envoyé, réduisez le nombre")

    @commands.command(pass_context=True, aliases=["rj", "rsa"])
    async def revenu(self, ctx):
        """Récupère les revenus personnels"""
        user = ctx.message.author
        server = ctx.message.server
        today = datetime.now().strftime("%d/%m/%Y")
        hier = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
        base_rj = 20
        base_jc = 5
        if await self.pay.verify(ctx):
            data = self.pay.get_account(user, True)
            if "RJ" not in data["PLUS"]:
                data["PLUS"]["RJ"] = {"last": None,
                                      "suite": []}
            if today != data["PLUS"]["RJ"]["last"]:
                money = self.pay.get_money_name(server, symbole=True)
                if data["PLUS"]["RJ"]["last"]:
                    then = datetime.strptime(data["PLUS"]["RJ"]["last"], "%d/%m/%Y")
                    delta_jour = (datetime.now() - then).days if (datetime.now() - then).days <= 7 else 7
                else:
                    delta_jour = 1
                data["PLUS"]["RJ"]["last"] = today
                if hier not in data["PLUS"]["RJ"]["suite"]:
                    data["PLUS"]["RJ"]["suite"] = [today]
                else:
                    if len(data["PLUS"]["RJ"]["suite"]) < 7:
                        data["PLUS"]["RJ"]["suite"].append(today)
                    else:
                        data["PLUS"]["RJ"]["suite"] = data["PLUS"]["RJ"]["suite"][1:]
                        data["PLUS"]["RJ"]["suite"].append(today)

                rj = base_rj * delta_jour
                save_txt = " (x{} jours)".format(delta_jour) if delta_jour > 1 else ""
                bonus_jc = (len(data["PLUS"]["RJ"]["suite"]) - 1) * base_jc
                if self.pay.get_account(user).solde >= 10000:
                    bonus_jc = 0
                    bonus_txt = "\n• **Bonus** \"Jours consécutif\" ─ Non percevable (+ 10 000)"
                else:
                    bonus_txt = "\n• **Bonus** \"Jours consécutif\" ─ **{}**{}".format(bonus_jc, money) if \
                        bonus_jc > 0 else ""
                self.pay.gain_credits(user, rj + bonus_jc, "Revenus")
                em = discord.Embed(title="Revenus",
                                   description="• **Revenu journalier** ─ **{}**{}{}{}".format(
                                       rj, money, save_txt, bonus_txt),
                                   color= user.color)
                em.set_footer(text="Iota Pay | Tu as désormais {} {}".format(self.pay.get_account(user).solde,
                                                                             self.pay.get_money_name(server, rj)))
                await self.bot.say(embed=em)
            else:
                await self.bot.say("**Refusé** ─ Tu as déjà pris ton revenu aujourd'hui")
        else:
            await self.bot.say("**Refusé** ─ Tu as besoin d'un compte valide pour demander un revenu")

    @commands.command(aliases=["mas"], pass_context=True)
    async def slot(self, ctx, offre: int = None):
        """Jouer à la machine à sous

        L'offre doit être comprise entre 10 et 300"""
        user = ctx.message.author
        server = ctx.message.server
        if not offre:
            txt = ":100: x3 = Offre x 100\n" \
                  ":gem: x3 = Offre x 30\n" \
                  ":gem: x2 = Offre + 300\n" \
                  ":four_leaf_clover: x3 = Offre x 12\n" \
                  ":four_leaf_clover: x2 = Offre + 100\n" \
                  "**fruit** x3 = Offre x 4\n" \
                  "**fruit** x2 = Offre x 2\n" \
                  ":zap: x1 ou x2 = Gains nuls\n" \
                  ":zap: x3 = Offre x 200"
            em = discord.Embed(title="Gains possibles", description=txt)
            await self.bot.say(embed=em)
            return
        if not 10 <= offre <= 300:
            await self.bot.say("**Offre invalide** | Elle doit être comprise entre 10 et 300.")
            return
        base = offre
        if await self.pay.verify(ctx):
            if self.pay.enough_credits(user, offre):
                cool = self.pay.get_cooldown(user, "slot")
                if not cool:
                    self.pay.add_cooldown(user, "slot", 20)
                    roue = [":zap:", ":gem:", ":cherries:", ":strawberry:", ":watermelon:", ":tangerine:", ":lemon:",
                            ":four_leaf_clover:", ":100:"]
                    plus_after = [":zap:", ":gem:", ":cherries:"]
                    plus_before = [":lemon:", ":four_leaf_clover:", ":100:"]
                    roue = plus_before + roue + plus_after
                    cols = []
                    for i in range(3):
                        n = random.randint(3, 11)
                        cols.append([roue[n - 1], roue[n], roue[n + 1]])
                    centre = [cols[0][1], cols[1][1], cols[2][1]]
                    disp = "**Offre:** {}{}\n\n".format(base, self.pay.get_money_name(server, symbole=True))
                    disp += "{}|{}|{}\n".format(cols[0][0], cols[1][0], cols[2][0])
                    disp += "{}|{}|{} **<<<**\n".format(cols[0][1], cols[1][1], cols[2][1])
                    disp += "{}|{}|{}\n".format(cols[0][2], cols[1][2], cols[2][2])
                    c = lambda x: centre.count(":{}:".format(x))
                    if ":zap:" in centre:
                        if c("zap") == 3:
                            offre *= 200
                            gaintxt = "3x ⚡ ─ Tu gagnes {} {}"
                        else:
                            offre = 0
                            gaintxt = "Tu t'es fait ⚡ ─ Tu perds ta mise !"
                    elif c("100") == 3:
                        offre *= 100
                        gaintxt = "3x 💯 ─ Tu gagnes {} {}"
                    elif c("gem") == 3:
                        offre *= 30
                        gaintxt = "3x 💎 ─ Tu gagnes {} {}"
                    elif c("gem") == 2:
                        offre += 300
                        gaintxt = "2x 💎 ─ Tu gagnes {} {}"
                    elif c("four_leaf_clover") == 3:
                        offre *= 12
                        gaintxt = "3x 🍀 ─ Tu gagnes {} {}"
                    elif c("four_leaf_clover") == 2:
                        offre += 100
                        gaintxt = "2x 🍀 ─ Tu gagnes {} {}"
                    elif c("cherries") == 3 or c("strawberry") == 3 or c("watermelon") == 3 or c("tangerine") == 3 or c(
                            "lemon") == 3:
                        offre *= 4
                        gaintxt = "3x un fruit ─ Tu gagnes {} {}"
                    elif c("cherries") == 2 or c("strawberry") == 2 or c("watermelon") == 2 or c("tangerine") == 2 or c(
                            "lemon") == 2:
                        offre *= 2
                        gaintxt = "2x un fruit ─ Tu gagnes {} {}"
                    else:
                        offre = 0
                        gaintxt = "Perdu ─ Tu perds ta mise !"

                    intros = ["Ça tourne", "Croisez les doigts", "Peut-être cette fois-ci", "Alleeeezzz",
                              "Ah les jeux d'argent", "Les dés sont lancés", "Il vous faut un peu de CHANCE",
                              "C'est parti", "Bling bling", "Le début de la richesse"]
                    intro = random.choice(intros)
                    if base == 69: intro = "Oh, petit cochon"
                    if base == 42: intro = "La réponse à la Vie, l'Univers et tout le reste"
                    if base == 28: intro = "Un nombre parfait pour jouer"
                    if base == 161: intro = "Le nombre d'or pour porter chance"
                    msg = None
                    for i in range(3):
                        points = "•" * (i + 1)
                        txt = "**Machine à sous** ─ {} {}".format(intro, points)
                        if not msg:
                            msg = await self.bot.say(txt)
                        else:
                            await self.bot.edit_message(msg, txt)
                        await asyncio.sleep(0.6)
                    if offre > 0:
                        gain = offre - base
                        self.pay.gain_credits(user, gain, "Gain machine à sous")
                        em = discord.Embed(title="Machine à sous ─ {}".format(user.name), description=disp,
                                           color=0x49ff6a)
                    else:
                        self.pay.perte_credits(user, base, "Perte machine à sous")
                        em = discord.Embed(title="Machine à sous ─ {}".format(user.name), description=disp,
                                           color=0xff4971)
                    em.set_footer(text=gaintxt.format(offre, self.pay.get_money_name(server, symbole=True)))
                    await self.bot.delete_message(msg)
                    await self.bot.say(embed=em)
                else:
                    await self.bot.say("**Cooldown** ─ Patientez encore {}".format(cool.string))
            else:
                await self.bot.say("**Solde insuffisant** ─ Réduisez votre offre si possible")
        else:
            await self.bot.say("**Refusé** ─ Tu as besoin d'un compte *Iota Pay* valide y jouer")

    @commands.group(name="modpay", aliases=["modbank", "mb"], pass_context=True)
    @checks.admin_or_permissions(ban_members=True)
    async def _modpay(self, ctx):
        """Paramètres de Iota Pay"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_modpay.command(pass_context=True)
    async def migration(self, ctx, source: discord.Member, destinataire: discord.Member):
        """Migre le compte d'un membre source à un membre destinataire"""
        if self.pay.get_account(source, ignore_close=True):
            if self.pay.account_migration(source, destinataire):
                await self.bot.say("**Migration effectuée** ─ Le compte appartient désormais à {}".format(
                    destinataire.name))
            else:
                await self.bot.say("**Erreur** ─ La migration à échouée")
        await self.bot.say("**Impossible** ─ Le membre source n'a pas de compte à migrer")

    @_modpay.command(pass_context=True)
    async def monnaie(self, ctx, *champs):
        """Changer le nom de la monnaie et son symbole

        Format: singuler/pluriel/symbole
        Ex: crédit/crédits/cdts"""
        champs = " ".join(champs)
        server = ctx.message.server
        data = self.pay.get_server_sys(server, True)
        if "/" in champs:
            splitted = champs.split("/")
            if len(splitted) == 3:
                data["MONNAIE"]["SINGULIER"] = splitted[0]
                data["MONNAIE"]["PLURIEL"] = splitted[1]
                data["MONNAIE"]["SYMBOLE"] = splitted[2]
                self.pay.forcesave()
                txt = "• Singulier: {}\n" \
                      "• Pluriel: {}\n" \
                      "• Symbole: {}".format(splitted[0], splitted[1], splitted[2])
                em = discord.Embed(title="Changement de monnaie", description=txt)
                em.set_footer(text="La monnaie sur ce serveur à été changée avec succès !")
                await self.bot.say(embed=em)
            else:
                await self.bot.say("**Aide pour le format** ─ *singulier*/*pluriel*/*symbole*")
        else:
            await self.bot.say("**Aide pour le format** ─ *singulier*/*pluriel*/*symbole*")

    @_modpay.command(pass_context=True)
    async def forcenew(self, ctx, user: discord.Member):
        """Ouvre de force un compte Iota Pay à un membre"""
        if not self.pay.get_account(user, ignore_close=True):
            self.pay.new_account(user)
            await self.bot.say("**Succès** ─ Le compte bancaire de {} à été créé".format(user.mention))
        else:
            await self.bot.say("**Erreur** ─ Ce membre possède déjà un compte bancaire")

    @_modpay.command(pass_context=True)
    async def deleteuser(self, ctx, user: discord.Member):
        """Supprime le compte bancaire d'un membre"""
        if self.pay.get_account(user, ignore_close=True):
            self.pay.reset_user_data(user)
            await self.bot.say("**Succès** ─ Le compte du membre a été effacé")
        else:
            await self.bot.say("**Erreur** ─ Le membre ne possède pas de compte bancaire")

    @_modpay.command(pass_context=True)
    async def resetserveur(self, ctx):
        """Reset les données du serveur, y compris la monnaie et les comptes bancaires des membres"""
        self.pay.reset_all_data(ctx.message.server)
        await self.bot.say("**Succès** ─ Toutes les données du serveur ont été reset")

    @_modpay.command(pass_context=True)
    @checks.admin_or_permissions(administrator=True)
    async def block(self, ctx, user: discord.Member):
        """Bloque le compte d'un membre"""
        data = self.pay.get_account(user, ignore_close=True)
        if data.open:
            self.pay.get_account(user, True, ignore_close=True)["OPEN"] = False
            await self.bot.say("**Compte fermé** ─ Ce membre ne pourra plus utiliser son compte")
        else:
            self.pay.get_account(user, True, ignore_close=True)["OPEN"] = True
            await self.bot.say("**Compte rouvert** ─ Ce membre peut de nouveau utiliser son compte")
        self.pay.forcesave()

    @_modpay.command(pass_context=True)
    @checks.admin_or_permissions(administrator=True)
    async def grant(self, ctx, user: discord.Member, somme: int, *raison):
        """Donne de l'argent à un membre"""
        server = ctx.message.server
        raison = "Ajout par administrateur" if not raison else " ".join(raison)
        if somme > 0:
            if self.pay.get_account(user, ignore_close=True):
                self.pay.gain_credits(user, somme, raison)
                await self.bot.say("**Succès** ─ {}{} ont été donnés au membre".format(somme, self.pay.get_money_name(
                    server, symbole=True)))
            else:
                await self.bot.say("**Erreur** ─ Le membre visé n'a pas de compte")
        else:
            await self.bot.say("**Erreur** ─ La somme doit être positive")

    @_modpay.command(pass_context=True)
    @checks.admin_or_permissions(administrator=True)
    async def take(self, ctx, user: discord.Member, somme: int, *raison):
        """Retire de l'argent à un membre"""
        server = ctx.message.server
        raison = "Retrait par administrateur" if not raison else " ".join(raison)
        if somme > 0:
            if self.pay.get_account(user, ignore_close=True):
                if not self.pay.enough_credits(user, somme):
                    somme = self.pay.get_account(user, ignore_close=True).solde
                self.pay.perte_credits(user, somme, raison)
                await self.bot.say("**Succès** ─ {}{} ont été retirés au membre".format(somme, self.pay.get_money_name(
                    server, symbole=True)))
            else:
                await self.bot.say("**Erreur** ─ Le membre visé n'a pas de compte")
        else:
            await self.bot.say("**Erreur** ─ La somme doit être positive")

    @_modpay.command(pass_context=True)
    @checks.admin_or_permissions(administrator=True)
    async def set(self, ctx, user: discord.Member, somme: int, *raison):
        """Modifie le solde d'un membre"""
        server = ctx.message.server
        raison = "Changement par administrateur" if not raison else " ".join(raison)
        if somme >= 0:
            if self.pay.get_account(user, ignore_close=True):
                self.pay.set_credits(user, somme, raison)
                await self.bot.say("**Succès** ─ Le membre possède désormais {} {}".format(
                    somme, self.pay.get_money_name(server, self.pay.get_account(user, ignore_close=True).solde)))
            else:
                await self.bot.say("**Erreur** ─ Le membre visé n'a pas de compte")
        else:
            await self.bot.say("**Erreur** ─ La somme doit être positive ou nulle")

    @_modpay.command(pass_context=True, hidden=True)
    async def backupcapital(self, ctx):
        """Permet de backup les données du module Capital pour ce serveur"""
        server = ctx.message.server
        if self.pay.backup_capitalAPI(server):
            await self.bot.say("**Succès** | Les données de Capital ont été importées et traitées")
        else:
            await self.bot.say("**Erreur** | Les données de Capital n'ont pas été importées")


def check_folders():
    if not os.path.exists("data/pay"):
        print("Creation du fichier Pay ...")
        os.makedirs("data/pay")


def check_files():
    if not os.path.isfile("data/pay/data.json"):
        print("Création de pay/data.json ...")
        fileIO("data/pay/data.json", "save", {})


def setup(bot):
    check_folders()
    check_files()
    n = Pay(bot)
    bot.add_cog(n)