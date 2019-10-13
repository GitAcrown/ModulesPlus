import asyncio
import operator
import os
import random
import string
import time
import discord
from collections import namedtuple
from datetime import datetime, timedelta

from __main__ import send_cmd_help
from discord.ext import commands

from .utils import checks
from .utils.dataIO import fileIO, dataIO


class WalletAPI:
    """API Wallet • Système de monnaie virtuelle"""

    def __init__(self, bot, path):
        self.bot = bot
        self.data = dataIO.load_json(path)
        self.cooldown = {}
        self.auto_save = 0
        self.import_from_pay()

    def save(self, force: bool = False):
        if force:
            fileIO("data/wallet/data.json", "save", self.data)
        elif (time.time() - self.auto_save) > 30: # 30 secondes
            fileIO("data/wallet/data.json", "save", self.data)
            self.auto_save = time.time()

    def pong(self):
        return datetime.now()

    def import_from_pay(self, force: bool = False):
        """Réimporte les informations à partir de Pay"""
        try:
            pay = dataIO.load_json("data/pay/data.json")
            for server in pay:
                if server not in self.data or force:
                    self.data[server] = {"USERS": {},
                                         "GUILDS": {},
                                         "SYS": {"roles_settings": {},
                                                 "booster": None,
                                                 "online": False}}
                    for user in pay[server]["USERS"]:
                        data = pay[server]["USERS"][user]
                        self.data[server]["USERS"][user] = {"solde": data["solde"],
                                                            "logs": [],
                                                            "cache": {}}
                    if "booster_role" in pay[server]["SYS"]:
                        self.data[server]["SYS"]["booster"] = pay[server]["SYS"]["booster_role"]
            self.save(True)
            return True
        except:
            return False

    # SERVER ------------------------------
    def get_server(self, server: discord.Server, sub=None, reset: bool = False):
        """Renvoie les données brutes du serveur"""
        if server.id not in self.data or reset:
            self.data[server.id] = {"USERS": {},
                                    "GUILDS": {},
                                    "SYS": {"roles_settings": {},
                                            "booster": None,
                                            "online": False}}
            self.save(True)
        return self.data[server.id][sub] if sub else self.data[server.id]

    def total_credits_on(self, server: discord.Server):
        if server.id in self.data:
            return sum([self.data[server.id]["USERS"][user]["solde"] for user in self.data[server.id]["USERS"]])
        return 0

    def total_accounts_on(self, server: discord.Server):
        """Renvoie le nombre de comptes inscrits à Wallet sur ce serveur"""
        if server.id in self.data:
            return len(self.data[server.id]["USERS"])
        return 0

    def get_top(self, server: discord.Server, limit: int = 20):
        """Renvoie un top des plus rihes du serveur"""
        if server.id in self.data:
            results = {}
            for user in self.data[server.id]["USERS"]:
                results[user] = self.data[server.id]["USERS"][user]["solde"]
            return sorted(results.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        return False

    def top_find(self, user: discord.Member):
        """Retrouve la place du membre dans le top de son serveur"""
        server = user.server
        if server.id in self.data:
            results = {}
            for u in self.data[server.id]["USERS"]:
                results[u] = self.data[server.id]["USERS"][u]["solde"]
            sort = sorted(results.items(), key=lambda kv: kv[1], reverse=True)
            for i in sort:
                if user.id == i[0]:
                    return sort.index(i) + 1
        return False

    # USER --------------------------------
    def get_account(self, user: discord.Member, raw: bool = False):
        """Renvoie le compte d'un membre"""
        registre = self.get_server(user.server, "USERS")
        if user.id in registre:
            return registre[user.id] if raw else self._obj_account(registre[user.id])
        return {}

    def create_account(self, user: discord.Member):
        """Création d'un nouveau compte Wallet"""
        registre = self.get_server(user.server, "USERS")
        if user.id not in registre:
            registre[user.id] = {"solde": 500,
                                 "logs": [],
                                 "cache": {}}
            self.save(True)
        return registre[user.id]

    def _obj_account(self, user_dict: dict):
        """Compte brut -> WalletAccount()"""
        userid = False
        for server in self.data:
            for user in self.data[server]["USERS"]:
                if self.data[server]["USERS"][user] == user_dict:
                    userid = user
        solde = user_dict["solde"]
        logs = []
        for l in user_dict["logs"]:
            logs.append(self._obj_transfer(l))
        cache = user_dict["cache"]
        WalletAccount = namedtuple("WalletAccount", ["solde", "logs", "cache", "id"])
        return WalletAccount(solde, logs, cache, userid)

    def get_all_accounts(self, server: discord.Server = None, raw: bool = False):
        """Renvoie tous les comptes d'un serveur ou de tous les serveurs si non spécifié"""
        accounts = []
        if server:
            s = self.get_server(server, "USERS")
            for u in s:
                if raw:
                    accounts.append(s[u])
                else:
                    accounts.append(self._obj_account(s[u]))
        else:
            for s in self.data:
                for u in s["USERS"]:
                    if raw:
                        accounts.append(s["USERS"][u])
                    else:
                        accounts.append(self._obj_account(s["USERS"][u]))
        return accounts

    async def sign_up(self, user: discord.Member):
        """Vérifie si le membre possède un compte

        - Si c'est le cas, le connecte
        - Si ce n'est pas le cas, lui propose d'un ouvrir un"""
        if not self.get_account(user):
            msg = await self.bot.say(">>> **Vous n'avez pas de compte Wallet**\n"
                                     "Voulez-vous en ouvrir un pour profiter de l'économie virtuelle de ce serveur ?")
            await self.bot.add_reaction(msg, "✔")
            await self.bot.add_reaction(msg, "✖")
            await self.bot.add_reaction(msg, "❔")
            await asyncio.sleep(0.2)

            def check(reaction, user):
                return not user.bot

            rep = await self.bot.wait_for_reaction(["✔", "✖", "❔"], message=msg, timeout=15, check=check, user=user)
            if rep is None or rep.reaction.emoji == "✖":
                await self.bot.clear_reactions(msg)
                txt = ">>> **Création de compte Wallet annulée**\nVous pourrez en ouvrir un plus tard avec `;wallet new`"
                await self.bot.edit_message(msg, txt)
                return False
            elif rep.reaction.emoji == "✔":
                await self.bot.clear_reactions(msg)
                if self.create_account(user):
                    txt = ">>> **Compte Wallet créé avec succès**\n" \
                          "Vous pouvez désormais profiter des fonctionnalités liées à l'économie virtuelle !"
                    await self.bot.edit_message(msg, txt)
                    return True
                else:
                    txt = ">>> **Création de compte Wallet impossible**\n" \
                          "Réessayez plus tard avec `;wallet new`"
                    await self.bot.edit_message(msg, txt)
                    return False
            elif rep.reaction.emoji == "❔":
                await self.bot.clear_reactions(msg)
                txt = ">>> **Informations concernant Wallet**\n" \
                      "`Wallet` est une extension de ce bot venant ajouter un système économique virtuel dans le serveur. " \
                      "Il permet de participer à des jeux ou évènements liés à celui-ci. La monnaie utilisée, " \
                      "le `Gold` ou `g` est une monnaie virtuelle qui ne peut être échangée contre de l'argent réelle.\n" \
                      "**Ouvrir un compte Wallet ?**"
                msg = await self.bot.edit_message(msg, txt)
                rep = await self.bot.wait_for_reaction(["✔", "✖"], message=msg, timeout=30, check=check, user=user)
                if rep is None or rep.reaction.emoji == "✖":
                    await self.bot.clear_reactions(msg)
                    txt = ">>> **Création de compte Wallet annulée**\nVous pourrez en ouvrir un plus tard avec `;wallet new`"
                    await self.bot.edit_message(msg, txt)
                    return False
                elif rep.reaction.emoji == "✔":
                    await self.bot.clear_reactions(msg)
                    if self.create_account(user):
                        txt = ">>> **Compte Wallet créé avec succès**\n" \
                              "Vous pouvez désormais profiter des fonctionnalités liées à l'économie virtuelle !"
                        await self.bot.edit_message(msg, txt)
                        return True
                    else:
                        txt = ">>> **Création de compte Wallet impossible**\n" \
                              "Réessayez plus tard avec `;wallet new`"
                        await self.bot.edit_message(msg, txt)
                        return False
        return True

    # ROLES -----------------------------------------
    def set_role(self, role: discord.Role, bonus_rj: int=0, price: int=0, special=None):
        """Change les paramètres du rôle Wallet sur le serveur"""
        if special == None:
            special = []
        sys = self.get_server(role.server, "SYS")["roles_settings"]
        sys[role.id] = {"bonus_rj": bonus_rj,
                        "price": price,
                        "special": special}
        if bonus_rj == 0 and price == 0 and not special:
            del sys[role.id]
            return False
        self.save()
        return sys[role.id]

    def get_role(self, role: discord.Role):
        """Renvoie les paramètres d'un rôle Wallet"""
        server = role.server
        data = self.get_server(server, "SYS")["roles_settings"]
        if role.id in data:
            return data[role.id]
        return {}

    def purge_roles(self, server: discord.Server):
        """Supprime les paramètres des rôles qui ne sont plus présents sur le serveur"""
        data = self.get_server(server, "SYS")["roles_settings"]
        for r in data:
            if r not in [r.id for r in server.roles]:
                del data[r]
        self.save()

    def search_roles(self, server: discord.Server, special: str):
        """Recherche les rôles correspondant au spécial visé"""
        sys = self.get_server(server, "SYS")["roles_settings"]
        liste = []
        for role in server.roles:
            if role.id in sys:
                if special in sys[role.id]["special"]:
                    liste.append(role)
        return liste

    # VIREMENTS -------------------------------------
    def _obj_transfer(self, transfer: list):
        """Virement brute -> WalletTransfer"""
        WalletTransfer = namedtuple('WalletTransfer', 'id, timestamp, somme, tags, desc, link')
        return WalletTransfer(transfer[0], self.ttd(transfer[1]), transfer[3], transfer[2], transfer[4], transfer[5])

    def new_transfer(self, user: discord.Member, somme: int, desc: str, tags: list = None):
        """Ajoute un virement à un membre"""
        data = self.get_account(user, True)
        if data:
            timestamp = datetime.now().timestamp()
            trs_id = str(''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(5)))
            while self.get_transfer(trs_id):
                trs_id = str(
                    ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(5)))
            if somme > 0: tags.append("gain")
            elif somme < 0: tags.append("perte")
            else: tags.append("nul")
            event = [trs_id, timestamp, tags, somme, desc, []]
            data["logs"].append(event)
            if len(data["logs"]) > 50:
                data["logs"].remove(data["logs"][0])
            self.save()
            return self._obj_transfer(event)
        return False

    def link_transfers(self, trs_list: list):
        for trs in trs_list:
            obj = self.get_transfer(trs, True)
            if obj:
                link = trs_list.copy()
                link.remove(trs)
                obj[5].extend(link)
            else: return False
        self.save()
        return True

    def get_transfer(self, trs_id: str, raw: bool = False):
        for server in self.data:
            for user in self.data[server]["USERS"]:
                for trs in self.data[server]["USERS"][user]["logs"]:
                    if trs[0] == trs_id:
                        return self._obj_transfer(trs) if not raw else trs
        return []

    def get_transfer_metadata(self, trs_id: str):
        """Renvoie le membre lié à une transaction peu importe le serveur où il se trouve"""
        server_id = user_id = None
        for server in self.data:
            for user in self.data[server]["USERS"]:
                if trs_id in [r[0] for r in self.data[server]["USERS"][user]["logs"]]:
                    server_id, user_id = server, user
        if server_id and user_id:
            server = self.bot.get_server(server_id)
            user = server.get_member(user_id)
            return user
        return None

    def get_transfers_from(self, user: discord.Member, nb: int = 1):
        """Renvoie les virements d'un membre"""
        data = self.get_account(user)
        if data and nb >= 1:
            logs = data.logs[::-1]
            return logs[:nb]
        return []

    def day_trs_from(self, user: discord.Member, jour: str = None):
        """Retourne les virements d'un jour d'un membre"""
        if not jour:
            jour = time.strftime("%d/%m/%Y", time.localtime())
        data = self.get_account(user)
        if data:
            liste = []
            for t in data.logs:
                if t.timestamp.jour == jour:
                    liste.append([t.timestamp.float, t])
            sort = sorted(liste, key=operator.itemgetter(0), reverse=True)
            return [i[1] for i in sort]
        return False

    def day_total_from(self, user: discord.Member, jour: str = None):
        """Retourne la valeur totale de tous les virements du jour visé"""
        trs = self.day_trs_from(user, jour)
        if trs:
            return sum([t.somme for t in trs])
        return 0

    # OPERATIONS ---------------------------------------
    def enough_credits(self, user: discord.Member, depense: int):
        """Vérifie que le membre possède assez de solde pour la transaction"""
        data = self.get_account(user)
        if data:
            return True if data.solde - depense >= 0 else False
        return False

    def add_credits(self, user: discord.Member, somme: int, desc: str, *tags):
        """Ajoute des crédits au membre"""
        data = self.get_account(user, True)
        if somme > 0:
            data["solde"] += int(somme)
            return self.new_transfer(user, somme, desc, [e for e in tags])
        return False

    def remove_credits(self, user: discord.Member, somme: int, desc: str, null: bool = False, *tags):
        """Retire les crédits à un membre"""
        somme = abs(round(somme))
        data = self.get_account(user, True)
        if self.enough_credits(user, somme):
            data["solde"] -= int(somme)
            return self.new_transfer(user, -somme, desc, [e for e in tags])
        elif null:
            somme = data["solde"]
            data["solde"] = 0
            return self.new_transfer(user, -somme, desc, [e for e in tags])
        return False

    def set_credits(self, user: discord.Member, somme: int, desc: str, *tags):
        """Change le solde d'un membre"""
        data = self.get_account(user, True)
        if somme >= 0:
            data["solde"] = round(somme)
            return self.new_transfer(user, somme, desc, [e for e in tags])
        return False

    def transfert_credits(self, debiteur: discord.Member, creancier: discord.Member, somme: int, desc: str, *tags):
        """Transfère des crédits d'un membre à un autre"""
        if debiteur != creancier:
            if somme > 0:
                if self.enough_credits(debiteur, somme):
                    don = self.remove_credits(debiteur, somme, desc, False, "transfert")
                    recu = self.add_credits(creancier, somme, desc, "transfert")
                    self.link_transfers([don, recu])
                    return (don, recu)
        return False

    # COOLDOWN -----------------------------------------
    def get_cooldown(self, user: discord.Member, name: str, raw: bool = False):
        """Renvoie le cooldown du membre sur ce module s'il y en a un"""
        server = user.server
        now = time.time()

        if server.id not in self.cooldown:
            self.cooldown[server.id] = {}
        if name.lower() not in self.cooldown[server.id]:
            self.cooldown[server.id][name.lower()] = {}

        rolecheck = self.search_roles(server, "kingcrimson")
        check = [n for n in user.roles if n.id in [u.id for u in rolecheck]]
        if check:
            return False # Pas de cooldown pour le cheatcode kingcrimson

        if user.id in self.cooldown[server.id][name.lower()]:
            if now <= self.cooldown[server.id][name.lower()][user.id]:
                duree = int(self.cooldown[server.id][name.lower()][user.id] - now)
                return self.timeformat(duree) if not raw else duree
            else:
                del self.cooldown[server.id][name.lower()][user.id]
        return False

    def add_cooldown(self, user: discord.Member, name: str, duree: int):
        """Attribue un cooldown à un membre sur une action visée (en secondes)"""
        server = user.server
        fin = time.time() + duree

        if server.id not in self.cooldown:
            self.cooldown[server.id] = {}
        if name.lower() not in self.cooldown[server.id]:
            self.cooldown[server.id][name.lower()] = {}

        if user.id in self.cooldown[server.id][name.lower()]:
            self.cooldown[server.id][name.lower()][user.id] += duree
        else:
            self.cooldown[server.id][name.lower()][user.id] = fin
        return self.get_cooldown(user, name)

    def reset_cooldown(self, user: discord.Member, name: str):
        """Remet un cooldown à 0"""
        server = user.server

        if server.id not in self.cooldown:
            self.cooldown[server.id] = {}
        if name.lower() not in self.cooldown[server.id]:
            self.cooldown[server.id][name.lower()] = {}

        if user.id in self.cooldown[server.id][name.lower()]:
            del self.cooldown[server.id][name.lower()][user.id]
            return True
        return False

    # GUILDES ------------------------------------------
    #TODO: Système de guildes

    # OUTILS -------------------------------------------
    def ttd(self, timestamp: float):  # Ex: Transforme 1547147012 en 2019, 1, 10, 20, 3, 44
        """Convertisseur timestamp-to-date"""
        UniTimestamp = namedtuple('UniTimestamp', ["raw", "heure", "jour", "float"])
        brut = datetime.fromtimestamp(timestamp)
        return UniTimestamp(brut, brut.strftime("%H:%M"), brut.strftime("%d/%m/%Y"), timestamp)

    def timeformat(self, val: int):
        """Converti automatiquement les secondes en unités plus pratiques"""
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
        return TimeConv(j, h, m, val, txt if txt else "< 1s")

    # RESET (DEBUG) -------------------------------------------
    def reset_user(self, user: discord.Member):
        """Reset les données d'un membre sur le serveur d'invocation"""
        server = user.server
        data = self.get_server(server, "USERS")
        if user.id in data:
            del data[user.id]
            self.save(True)
            return True
        return False

    def prune_users(self, server: discord.Server):
        """Purge les membres absents d'un serveur"""
        data = self.get_server(server, "USERS")
        allusers = [u.id for u in server.members]
        liste = []
        for uid in data:
            if uid not in allusers:
                del data[uid]
                liste.append(uid)
        self.save(True)
        return liste

    def reset_server(self, server: discord.Server):
        """Reset les données d'un serveur"""
        self.get_server(server, reset=True)
        return True

    def reset_all(self):
        """Reset les données de tous les serveurs inscrits"""
        self.data = {}
        self.save(True)
        return True

class Wallet: # MODULE WALLET =================================================================
    """Système monétaire virtuel"""

    def __init__(self, bot):
        self.bot = bot
        self.api = WalletAPI(bot, "data/wallet/data.json")
        # Pour importer l'API : self.bot.get_cog("Wallet").api

    def check(self, reaction, user):
        return not user.bot

    def __unload(self):
        self.api.save(True)
        print("Wallet - Sauvegarde effectuée")

    @commands.group(name="wallet", aliases=["w", "b"], pass_context=True, invoke_without_command=True, no_pm=True)
    async def wallet_account(self, ctx, membre: discord.Member = None):
        """Ensemble de commandes relatives à Wallet (économie virtuelle)

        En absence de mention, renvoie les détails du compte de l'invocateur"""
        if ctx.invoked_subcommand is None:
            if not membre:
                membre = ctx.message.author
            await ctx.invoke(self.account, user=membre)

    @wallet_account.command(pass_context=True)
    async def new(self, ctx):
        """Ouvre un nouveau compte Wallet"""
        data = self.api.get_account(ctx.message.author)
        if data:
            await self.bot.say("**Inutile** ─ Vous avez déjà un compte : consultez-le avec `;wallet`")
        else:
            await self.api.create_account(ctx.message.author)
            await self.bot.say("**Compte créé ─ Consultez-le avec `;wallet`")

    @wallet_account.command(pass_context=True)
    async def account(self, ctx, user: discord.Member = None):
        """Voir son Wallet

        [user] = Voir le compte du membre visé"""
        user = user if user else ctx.message.author
        same = True if user == ctx.message.author else False
        if same or self.api.get_account(user):
            if await self.api.sign_up(user):
                data = self.api.get_account(user)
                gains = self.api.day_total_from(user)
                gains = "+{}".format(gains) if gains >= 0 else "{}".format(gains)
                top = self.api.top_find(user) if self.api.top_find(user) else "Ø"

                txt = "\💵 **Solde** ─ {} gold{}\n".format(data.solde, "s" if data.solde > 1 else "")
                txt += "\💱 **Aujourd'hui** ─ {}\n".format(gains)
                txt += "\🏅 **Classement** ─ #{}\n".format(top)

                em = discord.Embed(title=user.name, description=txt, color=user.color, timestamp=ctx.message.timestamp)
                em.set_thumbnail(url=user.avatar_url)

                trs = self.api.get_transfers_from(user, 3)
                if trs:
                    reg = ""
                    for t in trs:
                        if t.somme < 0:
                            somme = str(t.somme)
                        else:
                            somme = "+" + str(t.somme)
                        desc = t.desc if len(t.desc) <= 30 else t.raison[:30] + "..."
                        reg += "`{}` · **{}** ─ *{}*\n".format(t.id, somme, desc)
                    em.add_field(name="Opérations", value=reg)
                await self.bot.say(embed=em)
            return
        await self.bot.say("Ce membre ne possède pas de compte *Wallet*.")

    #TODO: Recherche de logs avec tags

    @wallet_account.command(pass_context=True)
    async def logs(self, ctx, user: discord.Member = None, *search):
        """Recherche dans les dernières opérations d'un membre"""
        user = user if user else ctx.message.author
        data = self.api.get_account(user)
        if data:
            txt = "> Utilisez `;wallet get <id>` pour voir une opération en détails\n"
            page = 1
            jour = time.strftime("%d/%m/%Y", time.localtime())
            heure = time.strftime("%H:%M", time.localtime())
            for t in self.api.get_transfers_from(user, 50):
                ts = t.timestamp.jour
                if t.timestamp.jour == jour:
                    if t.timestamp.heure == heure:
                        ts = "À l'instant"
                    else:
                        ts = t.timestamp.heure
                txt += "{} » `{}` · **{}**g ─ *{}*\n".format(ts, t.id, t.somme, t.desc)
                if len(txt) > 1900 * page:
                    em = discord.Embed(title="Historique des opérations » {}".format(user), description=txt,
                                       color=user.color, timestamp=ctx.message.timestamp)
                    em.set_footer(text="Page n°{}".format(page))
                    await self.bot.say(embed=em)
                    txt = ""
                    page += 1
            if txt:
                em = discord.Embed(title="Historique des opérations » {}".format(user), description=txt,
                                   color=user.color, timestamp=ctx.message.timestamp)
                em.set_footer(text="Page n°{}".format(page))
                await self.bot.say(embed=em)
        else:
            await self.bot.say("Ce membre ne possède pas de compte *Wallet*.")

    @wallet_account.command(pass_context=True)
    async def get(self, ctx, operation_id: str):
        """Affiche les détails d'une opération bancaire"""
        if len(operation_id) == 5:
            trs = self.api.get_transfer(operation_id)
            if trs:
                details = self.api.get_transfer_metadata(trs.id)
                somme = trs.somme

                if trs.somme > 0:
                    somme = "+" + str(trs.somme)
                if trs.link:
                    link = " ".join(["`{}`".format(i) for i in trs.link])
                else:
                    link = "Aucune"

                if trs.tags:
                    tags = " ".join(["`{}`".format(i) for i in trs.tags])
                else:
                    tags = "Aucun"

                txt = "> *{}*\n" \
                      "**Tags** ─ {}\n" \
                      "**Somme** ─ {}g\n" \
                      "**Compte d'origine** ─ {}\n" \
                      "**Serveur** ─ {}\n" \
                      "**Opérations liées** ─ {}".format(trs.desc, tags, somme, details.name, details.server.name, link)
                em = discord.Embed(title="Détails de l'opération » {}".format(trs.id), description=txt,
                                   timestamp=trs.timestamp.brut)
                await self.bot.say(embed=em)
            else:
                await self.bot.say("Identifiant de l'opération introuvable ─ L'opération a peut-être expirée")
        else:
            await self.bot.say("Identifiant de l'opération invalide ─ "
                               "Les identifiants d'opérations sont composés de 5 symboles (chiffres & lettres)")


    @commands.command(pass_context=True, no_pm=True)
    async def give(self, ctx, creancier: discord.Member, somme: int, *raison):
        """Transférer de l'argent sur le compte d'un autre membre"""
        server = ctx.message.server
        debiteur = ctx.message.author
        raison = " ".join(raison) if raison else "Don de {} pour {}".format(debiteur, creancier)
        if somme > 0:
            if self.api.get_account(creancier):
                if await self.api.sign_up(debiteur):
                    if self.api.enough_credits(debiteur, somme):
                        txt = ">>> __**Transfert de crédits**__\n**{}** » `{}g` » **{}**".format(
                            debiteur.name, somme, creancier.name)
                        msg = await self.bot.say(txt)
                        if self.api.transfert_credits(debiteur, creancier, somme, raison):
                            await asyncio.sleep(3)
                            await self.bot.edit_message(msg, txt + "\n\n**Succès.**")
                        else:
                            await asyncio.sleep(1.5)
                            await self.bot.edit_message(msg, txt + "\n\n**Échec.** Réessayez plus tard.")
                    else:
                        await self.bot.say("Vous n'avez pas cette somme sur votre compte, soyez plus raisonnable.")
                else:
                    return
            else:
                await self.bot.say("Le membre visé ne possède pas de compte Wallet.")
        else:
            await self.bot.say("Impossible, la somme est nulle ou négative.")

    @commands.command(pass_context=True, no_pm=True, aliases=["palmares"])
    async def top(self, ctx, top: int = 10):
        """Affiche un top des membres les plus riches du serveur"""
        server = ctx.message.server
        author = ctx.message.author
        palm = self.api.get_top(server)
        n = 1
        txt = ""

        def medal(n):
            if n == 1:
                return " \🥇"
            elif n == 2:
                return " \🥈"
            elif n == 3:
                return " \🥉"
            else:
                return ""

        found = False
        if palm:
            for u in palm:
                if n < top:
                    try:
                        if n == 4:
                            txt += "──────────\n"
                        username = str(server.get_member(u[0]))
                        if username.lower() == "none":
                            username = str(await self.bot.get_user_info(u[0]))
                        if u[0] == author.id:
                            txt += "{}**{}** · {}g ─ *__{}__*\n".format(medal(n), n, u[1], username)
                            found = True
                        else:
                            txt += "{}**{}** · {}g ─ *{}*\n".format(medal(n), n, u[1], username)
                        n += 1
                    except:
                        continue
            if not found:
                data = self.api.get_account(author)
                if data:
                    place = self.api.top_find(author)
                    if place:
                        txt += "(...)\n{}**{}** · {}g ─ *__{}__*\n".format(medal(place), place, data.solde, author)
                    else:
                        txt += "(...)\nØ · {}g ─ *__{}__*\n".format(data.solde, author)

            em = discord.Embed(title="Top des plus riches du serveur", description=txt, timestamp=ctx.message.timestamp)
            total = self.api.total_credits_on(server)
            members = self.api.total_accounts_on(server)
            em.set_footer(text="Total = {}g avec {} comptes".format(total, members))
            try:
                await self.bot.say(embed=em)
            except:
                await self.bot.say("**Erreur** ─ Le classement est trop long pour être affiché sur Discord")
        else:
            await self.bot.say("**Erreur** ─ Aucun compte n'est présent sur ce serveur")

    @commands.command(pass_context=True, no_pm=True, aliases=["rj"])
    async def revenu(self, ctx):
        """Récupérer son revenu journalier"""
        user, server = ctx.message.author, ctx.message.server
        today = datetime.now().strftime("%d/%m/%Y")
        hier = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")

        # Afin de pouvoir modifier facilement
        rj = 100
        jc = 50

        if await self.api.sign_up(user):
            data = self.api.get_account(user, True)
            sys = self.api.get_server(server, "SYS")["roles_settings"]
            if "last_revenu" not in data["cache"]:
                data["cache"]["last_revenu"] = None
            total = 0
            txt = "```fix\n"

            if data["cache"]["last_revenu"] != today:
                total += rj
                txt += "+ {} » Base journalière\n"
                if data["cache"]["last_revenu"] == hier:
                    total += jc
                    txt += "+ {} » Jours consécutifs\n"
                data["cache"]["last_revenu"] = today

                for r in sys:
                    role = discord.utils.get(server.roles, id=r)
                    if role in user.roles:
                        if sys[r]["revenu_bonus"]:
                            total += sys[r]["revenu_bonus"]
                            txt += "+ {} » Rôle {}\n".format(sys[r]["revenu_bonus"], role.name)

                self.api.add_credits(user, total, "Récupération de revenus", "revenus")
                txt += "───────"
                txt += "= {}g```".format(total)

                em = discord.Embed(description=txt, color=user.color, timestamp=ctx.message.timestamp)
                em.set_author(name="Revenus", icon_url=user.avatar_url)
                em.set_footer(text="Solde = {}g".format(data["solde"]))
                await self.bot.say(embed=em)
            else:
                rolecheck = self.api.search_roles(server, "hermitpurple")
                check = [n for n in user.roles if n.id in [u.id for u in rolecheck]]
                if check:
                    await self.bot.say("Tes revenus sont récupérés automatiquement "
                                       "(lors de ton premier message chaque jour) grâce à un rôle que tu possèdes !")
                else:
                    await self.bot.say("Tu as déjà pris ton revenu aujourd'hui !")
        else:
            await self.bot.say("Tu as besoin d'un compte *Wallet* pour récupérer ton revenu.")

    # JEUX ====================================================================
    @commands.command(pass_context=True, aliases=["mas"])
    async def slot(self, ctx, offre: int = None):
        """Jouer à la machine à sous

        L'offre doit être comprise entre 10 et 500"""
        user = ctx.message.author
        server = ctx.message.server
        if not offre:
            txt = ":100: x3 = Offre x 50\n" \
                  ":gem: x3 = Offre x 20\n" \
                  ":gem: x2 = Offre X 10\n" \
                  ":four_leaf_clover: x3 = Offre x 12\n" \
                  ":four_leaf_clover: x2 = Offre x 4\n" \
                  "**fruit** x3 = Offre x 6\n" \
                  "**fruit** x2 = Offre x 3\n" \
                  ":zap: x1 ou x2 = Gains nuls\n" \
                  ":zap: x3 = Offre x 100"
            em = discord.Embed(title="Gains possibles", description=txt)
            await self.bot.say(embed=em)
            return
        if not 10 <= offre <= 500:
            await self.bot.say("**Offre invalide** ─ Elle doit être comprise entre 10 et 500.")
            return
        base = offre
        cooldown = 10
        if await self.api.sign_up(user):
            if self.api.enough_credits(user, offre):
                cool = self.api.get_cooldown(user, "slot")
                if not cool:
                    self.api.add_cooldown(user, "slot_antispam", 30)
                    if self.api.get_cooldown(user, "slot_antispam", True) > 90:
                        self.api.reset_cooldown(user, "slot_antispam")
                        self.api.add_cooldown(user, "slot_antispam", 20)
                        cooldown = 40
                    self.api.add_cooldown(user, "slot", cooldown)
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
                    disp = "**Offre:** {}G\n\n".format(base)
                    disp += "{}|{}|{}\n".format(cols[0][0], cols[1][0], cols[2][0])
                    disp += "{}|{}|{} **<<<**\n".format(cols[0][1], cols[1][1], cols[2][1])
                    disp += "{}|{}|{}\n".format(cols[0][2], cols[1][2], cols[2][2])
                    c = lambda x: centre.count(":{}:".format(x))
                    if ":zap:" in centre:
                        if c("zap") == 3:
                            offre *= 100
                            gaintxt = "3x ⚡ ─ Tu gagnes {} {}"
                        else:
                            offre = 0
                            gaintxt = "Tu t'es fait zap ⚡ ─ Tu perds ta mise !"
                    elif c("100") == 3:
                        offre *= 50
                        gaintxt = "3x 💯 ─ Tu gagnes {} {}"
                    elif c("gem") == 3:
                        offre *= 20
                        gaintxt = "3x 💎 ─ Tu gagnes {} {}"
                    elif c("gem") == 2:
                        offre *= 10
                        gaintxt = "2x 💎 ─ Tu gagnes {} {}"
                    elif c("four_leaf_clover") == 3:
                        offre *= 12
                        gaintxt = "3x 🍀 ─ Tu gagnes {} {}"
                    elif c("four_leaf_clover") == 2:
                        offre *= 4
                        gaintxt = "2x 🍀 ─ Tu gagnes {} {}"
                    elif c("cherries") == 3 or c("strawberry") == 3 or c("watermelon") == 3 or c("tangerine") == 3 or c(
                            "lemon") == 3:
                        offre *= 6
                        gaintxt = "3x un fruit ─ Tu gagnes {} {}"
                    elif c("cherries") == 2 or c("strawberry") == 2 or c("watermelon") == 2 or c("tangerine") == 2 or c(
                            "lemon") == 2:
                        offre *= 3
                        gaintxt = "2x un fruit ─ Tu gagnes {} {}"
                    else:
                        offre = 0
                        gaintxt = "Perdu ─ Tu perds ta mise !"

                    intros = ["Ça tourne", "Croisez les doigts", "Peut-être cette fois-ci", "Alleeeezzz",
                              "Ah les jeux d'argent", "Les dés sont lancés", "Il vous faut un peu de CHANCE",
                              "C'est parti", "Bling bling", "Le début de la richesse"]
                    intro = random.choice(intros)
                    if base == 69: intro = "Oh, petit cochon"
                    if base == 42: intro = "La réponse à la vie, l'univers et tout le reste"
                    if base == 28: intro = "Un nombre parfait pour jouer"
                    if base == 161: intro = "Le nombre d'or pour porter chance"
                    if base == 420: intro = "420BLAZEIT"
                    if base == 314: intro = "π."
                    msg = None
                    for i in range(3):
                        points = "•" * (i + 1)
                        txt = "**Machine à sous** ─ {} {}".format(intro, points)
                        if not msg:
                            msg = await self.bot.say(txt)
                        else:
                            await self.bot.edit_message(msg, txt)
                        await asyncio.sleep(0.4)
                    if offre > 0:
                        gain = offre - base
                        self.api.add_credits(user, gain, "Gain à la machine à sous", "slot")
                        em = discord.Embed(title="Machine à sous ─ {}".format(user.name), description=disp,
                                           color=0x49ff6a)
                    else:
                        self.api.remove_credits(user, base, "Perte à la machine à sous", False, "slot")
                        em = discord.Embed(title="Machine à sous ─ {}".format(user.name), description=disp,
                                           color=0xff4971)
                    em.set_footer(text=gaintxt.format(offre, "golds"))
                    await self.bot.delete_message(msg)
                    await self.bot.say(embed=em)
                else:
                    await self.bot.say("**Cooldown** ─ Slot possible dans {}".format(cool.string))
            else:
                await self.bot.say("**Solde insuffisant** ─ Réduisez votre offre si possible")
        else:
            await self.bot.say("Un compte Wallet est nécessaire pour jouer à la machine à sous.")

    # ROLES WALLET ====================================================================
    @commands.group(name="walletroles", aliases=["wr"], pass_context=True, no_pm=True)
    async def _wallet_roles(self, ctx):
        """Gestion des rôles Wallet"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_wallet_roles.command(pass_context=True)
    @checks.admin_or_permissions(ban_members=True)
    async def config(self, ctx, role: discord.Role, bonus_rj: int = 0, prix: int = 0, *special):
        """Change la configuration d'un rôle sur Wallet

        <bonus_rj> = Règle le bonus donné par le rôle lors de la collecte de son revenu (ne peut excéder 100)
        <prix> = Règle le prix d'achat du rôle, 0 si il ne peut pas être acheté
        [special] = Liste des capacités spécifiques offertes par la possession du rôle

        Exemples :
        ;wr config @Daladas 10 0 -> Donne un bonus de 10 crédits au ;rj
        ;wr config @Squadra 30 10000 -> Donne un bonus de 30 au ;rj et permet d'acheter le rôle à 10k crédits
        ;wr config @Normalfag 0 0 autorj -> Donne la capacité de recueillir automatiquement le ;rj (exemple fictif)
        ;wr config @Random -> Reset les paramètres du rôle"""
        server = discord.Server
        special = special if special else []
        if role in server.roles:
            if special:
                for i in special:
                    if i not in ["hermitpurple", "kingcrimson", "bitesthedust"]: # Chuuuuuut.
                        await self.bot.say("**Erreur** ─ Le code special `{}` n'existe pas.".format(i))
                        return
            self.api.set_role(role, bonus_rj, prix, special)
            await self.bot.say("**Succès** ─ Le rôle a été configuré selon les paramètres donnés")
        else:
            await self.bot.say("**Erreur** ─ Rôle introuvable ou inaccessible")

    @_wallet_roles.command(pass_context=True)
    async def shop(self, ctx, role: discord.Role = None):
        """Obtenir un rôle sur le serveur

        Faire la commande alors que vous possédez déjà ce rôle permet de le revendre"""
        server = ctx.message.server
        user = ctx.message.author
        sys = self.api.get_server(server, "SYS")
        self.api.purge_roles(server)
        if role:
            if role not in server.roles:
                await self.bot.say("Ce rôle n'existe pas ou ne m'est pas accessible.")
                return
            sysroles = sys["roles_settings"]
            if sysroles:
                if role.id in sysroles:
                    if sysroles[role.id]["price"] > 0:
                        if await self.api.sign_up(user):
                            if role in user.roles:
                                calc = round(sysroles[role.id]["price"] / 2)
                                txt = "Voulez-vous vendre le rôle {} ?\nVous obtiendrez 50% du prix d'origine, " \
                                      "c'est-à-dire **{}** golds.".format(role.name, calc)
                                em = discord.Embed(description=txt)
                                em.set_author(name="Boutique de rôles ─ Vente", icon_url=user.avatar_url)
                                dil = await self.bot.say(embed=em)
                                await asyncio.sleep(0.1)
                                await self.bot.add_reaction(dil, "✅")
                                await self.bot.add_reaction(dil, "❎")
                                rep = await self.bot.wait_for_reaction(["✅", "❎"], message=dil, timeout=30, user=user)
                                if rep is None or rep.reaction.emoji == "❎":
                                    await self.bot.delete_message(dil)
                                    await self.bot.say("**Transaction annulée**")
                                    return
                                else:
                                    await self.bot.clear_reactions(dil)
                                    await self.bot.remove_roles(user, role)
                                    self.api.add_credits(user, calc, "Vente de {}".format(role.name), "vente", "role")
                                    em.description = "Rôle ***{}*** vendu ! **{}** golds ont été transférés sur " \
                                                     "votre compte.".format(role.name, calc)
                                    await self.bot.edit_message(dil, embed=em)
                                    return
                            else:
                                if self.api.enough_credits(user, sysroles[role.id]["price"]):
                                    try:
                                        await self.bot.add_roles(user, role)
                                    except Exception as e:
                                        await self.bot.say("**Erreur** ─ L'opération ne s'est pas produite "
                                                           "comme prévue... (autorisation manquante)")
                                        print(e)
                                        return
                                    self.api.remove_credits(user, sysroles[role.id]["price"],
                                                            "Achat rôle {}".format(role.name), False, "achat", "role")
                                    await self.bot.say("Rôle ***{}*** obtenu avec succès !".format(role.name))
                                else:
                                    await self.bot.say("Vous n'avez pas assez de crédits pour obtenir ce rôle.")
                        else:
                            await self.bot.say("Un compte **Wallet** est nécessaire pour les rôles payants.")
                    else:
                        await self.bot.say("Ce rôle n'est pas vendu dans cette boutique, vous ne pouvez le revendre.")
                else:
                    await self.bot.say("Ce rôle n'est pas disponible dans la boutique.")
            else:
                await self.bot.say("Aucun rôle n'est disponible dans la boutique.")
        else:
            if sys["roles_settings"]:
                txt = ""
                for r in sys["roles_settings"]:
                    role = discord.utils.get(server.roles, id=r)
                    rolename = role.mention if role.mentionable else "**@{}**".format(role.name)
                    prix = sys["roles_settings"][role.id]["price"] if sys["roles_settings"][role.id]["price"] > 0 else "Indisponible"
                    txt += "{} ─ {} (BRJ = {})\n".format(rolename, prix, sys["roles_settings"][role.id]["bonus_rj"])
                em = discord.Embed(description=txt)
                em.set_author(name="Boutique de rôles ─ Liste", icon_url=user.avatar_url)
                em.set_footer(text="Obtenir un rôle = ;wr shop <role>")
                await self.bot.say(embed=em)
            else:
                await self.bot.say("Aucun rôle n'est disponible dans la boutique.")

    # COMMANDES UTILES =========================================================
    @commands.command(pass_context=True)
    async def resetday(self, ctx):
        """Retourne le compte à l'état qu'il était ce matin à 00h00

        N'efface pas les logs de ce qu'il s'est passé entre temps"""
        author = ctx.message.author
        if self.api.get_account(author):
            rolecheck = self.api.search_roles(ctx.message.server, "bitesthedust")
            check = [n for n in author.roles if n.id in [u.id for u in rolecheck]]
            if check:
                data = self.api.get_account(author)
                if "last_revenu" not in data["cache"]:
                    data["cache"]["last_revenu"] = None

                trs = self.api.day_total_from(author)
                today = datetime.now().strftime("%d/%m/%Y")
                if trs > 0:
                    self.api.remove_credits(author, trs, "Reset du {}".format(today), False, "reset")
                else:
                    self.api.add_credits(author, trs, "Reset du {}".format(today), "reset")
                await self.bot.say("**Reset effectué** ─ Votre solde a été rétabli à l'état qu'il était le {} à 00h00.".format(today))
        else:
            await self.bot.say("**Erreur** ─ Vous n'avez pas de compte Wallet.")

    # PARAMETRES ===============================================================
    @commands.group(name="modwallet", aliases=["mw"], pass_context=True, no_pm=True)
    @checks.admin_or_permissions(ban_members=True)
    async def _modwallet(self, ctx):
        """Gestion de la banque Wallet"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_modwallet.command(pass_context=True)
    async def forcenew(self, ctx, user: discord.Member):
        """Force l'ouverture du compte d'un membre"""
        if not self.api.get_account(user):
            self.api.create_account(user)
            await self.bot.say("Compte Wallet de {} créé.".format(user.mention))
        else:
            await self.bot.say("**Inutile** ─ Le membre possède déjà un compte Wallet")

    @_modwallet.command(pass_context=True)
    async def purge(self, ctx):
        """Purge les comptes Wallet des membres qui ne sont plus sur le serveur"""
        server = ctx.message.server

        def check(self, reaction, user):
            return not user.bot

        msg = await self.bot.say("**Attention** ─ Cette commande efface __définitivement__ les comptes Wallet des membres absents du serveur.\n"
                                 "Cette action est irréversible. Voulez-vous continuer ?")
        rep = await self.bot.wait_for_reaction(["✔", "✖"], message=msg, timeout=20, check=check, user=ctx.message.author)
        if rep is None or rep.reaction.emoji == "✖":
            await self.bot.delete_message(msg)
            await self.bot.say("**Purge annulée**")
        elif rep.reaction.emoji == "✔":
            await self.bot.delete_message(msg)
            l = self.api.prune_users(server)
            await self.bot.say("**Purge réalisée** ─ {} comptes ont été supprimés".format(len(l)))

    @_modwallet.command(pass_context=True)
    async def set(self, ctx, user: discord.Member, operation: str, *raison):
        """Change le solde d'un membre (+/-/=)

        Exemples :
        ;mw set @Acrone 42 -> Change le solde pour 42
        ;mw set @Acrone +15 -> Ajoute 15 crédits
        ;mw set @Acrone -30 -> Retire 30 crédits"""
        server = ctx.message.server
        raison = " ".join(raison) if raison else "Modification par modération"
        if self.api.get_account(user):
            if operation.isdigit():
                self.api.set_credits(user, int(operation), raison, "mod")
                data = self.api.get_account(user)
                await self.bot.say("**Solde modifié** ─ Le solde du membre est désormais de {}g".format(data.solde))
            elif operation.startswith("="):
                try:
                    operation = int(operation[1:])
                    self.api.set_credits(user, int(operation), raison, "mod")
                    data = self.api.get_account(user)
                    await self.bot.say("**Solde modifié** ─ Le solde du membre est désormais de {}g".format(data.solde))
                except:
                    await send_cmd_help(ctx)
                    return
            elif operation.startswith("+"):
                try:
                    operation = int(operation[1:])
                    self.api.add_credits(user, int(operation), raison, "mod")
                    data = self.api.get_account(user)
                    await self.bot.say("**Solde modifié** ─ Le solde du membre est désormais de {}g".format(data.solde))
                except:
                    await send_cmd_help(ctx)
                    return
            elif operation.startswith("-"):
                try:
                    operation = int(operation[1:])
                    self.api.remove_credits(user, int(operation), raison, True, "mod")
                    data = self.api.get_account(user)
                    await self.bot.say("**Solde modifié** ─ Le solde du membre est désormais de {}g".format(data.solde))
                except:
                    await send_cmd_help(ctx)
                    return
            else:
                await send_cmd_help(ctx)
        else:
            await self.bot.say("Le membre visé n'a pas de compte Wallet.")

    @_modwallet.command(pass_context=True)
    async def delete(self, ctx, user: discord.Member):
        """Supprime le compte d'un membre"""
        if self.api.get_account(user):
            self.api.reset_user(user)
            await self.bot.say("Le compte du membre a été effacé.")
        else:
            await self.bot.say("Le membre ne possède pas de compte Wallet")

    @_modwallet.command(pass_context=True, hidden=True)
    async def deleteall(self, ctx):
        """Reset les données du serveur"""
        self.api.reset_server(ctx.message.server)
        await self.bot.say("Données du serveur reset.")

    @_modwallet.command(pass_context=True, hidden=True)
    @checks.is_owner()
    async def totalreset(self, ctx):
        """Efface toutes les données du module"""
        self.api.reset_all()
        await self.bot.say("**Données du module reset.**")

    @_modwallet.command(pass_context=True, hidden=True)
    @checks.is_owner()
    async def globalimport(self, ctx):
        """Réimporte les données de Pay (13/10/2019)"""
        self.api.import_from_pay(True)
        await self.bot.say("**Données du module Pay importées.**")

    async def onmessage(self, message):
        author = message.author
        data = self.api.get_account(author, True)
        if data:
            today = datetime.now().strftime("%d/%m/%Y")
            hier = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")

            if data["cache"].get("last_revenu", hier) != today:
                server = message.server
                rolecheck = self.api.search_roles(server, "hermitpurple")
                check = [n for n in author.roles if n.id in [u.id for u in rolecheck]]
                if check:
                    sys = self.api.get_server(server, "SYS")["roles_settings"]
                    total = 100
                    data["cache"]["last_revenu"] = today

                    for r in sys:
                        role = discord.utils.get(server.roles, id=r)
                        if role in author.roles:
                            if sys[r]["revenu_bonus"]:
                                total += sys[r]["revenu_bonus"]
                    self.api.add_credits(author, total, "Récupération automatique de revenus", "revenus", "auto")


def check_folders():
    if not os.path.exists("data/wallet"):
        print("Creation du dossier Wallet ...")
        os.makedirs("data/wallet")


def check_files():
    if not os.path.isfile("data/wallet/data.json"):
        print("Ouverture de wallet/data.json ...")
        fileIO("data/wallet/data.json", "save", {})


def setup(bot):
    check_folders()
    check_files()
    n = Wallet(bot)
    bot.add_listener(n.onmessage, "on_message")
    bot.add_cog(n)
