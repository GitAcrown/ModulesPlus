import asyncio
import operator
import os
import random
import string
import time
from collections import namedtuple
from datetime import datetime, timedelta

import discord
from __main__ import send_cmd_help
from discord.ext import commands

from .utils import checks
from .utils.dataIO import fileIO, dataIO

# Ce module est volontairement "sur-commenté" dans un soucis de lisibilité et afin que certaines personnes puisse
# s'en servir de base
palette = {"lighter": 0x34bba7,
           "light" : 0x219d7e,
           "dark": 0x2c7972,
           "warning": 0xfb4e4e,
           "info": 0xFFDD94,
           "stay": 0xfff952}
goldimg = "https://i.imgur.com/IoRv050.png"

class PayAPI:
    """API Turing Pay | Système de monnaie globale par serveur"""

    def __init__(self, bot, path):
        self.bot = bot
        self.data = dataIO.load_json(path)
        self.meta = {"last_save": 0}
        self.cooldown = {}

    def save(self, force: bool = False):
        if force:
            fileIO("data/pay/data.json", "save", self.data)
        elif (time.time() - self.meta["last_save"]) > 30: # 30 secondes
            fileIO("data/pay/data.json", "save", self.data)
            self.meta["last_save"] = time.time()

    def pong(self):
        """Envoie un PONG permettant de vérifier si l'API est connectée à un autre module"""
        return datetime.now()

    def ttd(self, timestamp: float):  # Ex: Transforme 1547147012 en 2019, 1, 10, 20, 3, 44
        """Convertisseur timestamp-to-date"""
        UniTimestamp = namedtuple('UniTimestamp', ["brut", "heure", "jour", "float"])
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
        return TimeConv(j, h, m, val, txt)

    def get_server(self, server: discord.Server, sub: str = None, reset: bool = False):
        """Renvoie les données du serveur"""
        if server.id not in self.data or reset:
            self.data[server.id] = {"USERS": {},
                                    "SYS": {},
                                    "MARKET": {}}
            self.save(True)
        return self.data[server.id][sub] if sub else self.data[server.id]


    def obj_account(self, user_dict: dict):
        """Transforme les données brutes d'un profil en Namedtuple facile à exploiter"""
        userid = False
        for server in self.data:
            for user in self.data[server]["USERS"]:
                if self.data[server]["USERS"][user] == user_dict:
                    userid = user
        solde = user_dict["solde"]
        logs = []
        for l in user_dict["logs"]:
            logs.append(self.obj_transaction(l))
        inventory = user_dict["inventory"]
        cache = user_dict["cache"]
        PayAccount = namedtuple("PayAccount", ["solde", "logs", "inventory", "cache", "userid"])
        return PayAccount(solde, logs, inventory, cache, userid)

    def create_account(self, user: discord.Member):
        """Créer un nouveau compte Pay"""
        data = self.get_server(user.server, "USERS")
        if user.id not in data:
            data[user.id] = {"solde": 500,
                             "logs": [],
                             "inventory" : {},
                             "cache": {}}
            self.save(True)
        return data[user.id]

    def get_account(self, user: discord.Member, tuple: bool = False):
        """Renvoie le compte d'un membre s'il en possède un"""
        data = self.get_server(user.server, "USERS")
        if user.id in data:
            return data[user.id] if not tuple else self.obj_account(data[user.id])
        return False

    def get_all_accounts(self, server: discord.Server = None):
        liste = []
        if server:
            serv = self.get_server(server, "USERS")
            for u in serv:
                liste.append(self.obj_account(serv[u]))
            return liste
        else:
            for serv in self.data:
                for u in serv["USERS"]:
                    liste.append(self.obj_account(serv["USERS"][u]))
            return liste

    async def account_dial(self, user: discord.Member):
        """S'inscrire sur le système Pay du serveur"""
        if not self.get_account(user):
            em = discord.Embed(description="{} ─ Vous n'avez pas de compte **Pay**, voulez-vous en ouvrir un ?".format(
                user.mention), color=palette["light"])

            msg = await self.bot.say(embed=em)
            await self.bot.add_reaction(msg, "✔")
            await self.bot.add_reaction(msg, "✖")
            await self.bot.add_reaction(msg, "❔")
            await asyncio.sleep(0.1)

            def check(reaction, user):
                return not user.bot

            rep = await self.bot.wait_for_reaction(["✔", "✖", "❔"], message=msg, timeout=20, check=check,
                                                   user=user)
            if rep is None or rep.reaction.emoji == "✖":
                await self.bot.clear_reactions(msg)
                em = discord.Embed(
                    description="{} ─ Annulé, vous pourrez en ouvrir un plus tard avec `.pay new`".format(
                        user.mention), color=palette["dark"])
                await self.bot.edit_message(msg, embed=em)
                await asyncio.sleep(5)
                await self.bot.delete_message(msg)
                return False
            elif rep.reaction.emoji == "✔":
                if self.create_account(user):
                    await self.bot.clear_reactions(msg)
                    em = discord.Embed(
                        description="{} ─ Votre compte à été ouvert, vous pouvez désormais profiter des "
                                    "fonctionnalités économiques.".format(
                            user.mention), color=palette["lighter"])
                    await self.bot.edit_message(msg, embed=em)
                    return True
                else:
                    em = discord.Embed(
                        description="{} ─ Je n'ai pas réussi à vous ouvrir un compte.\n"
                                    "Réessayez plus tard avec `.pay new`".format(
                            user.mention), color=palette["warning"])
                    await self.bot.edit_message(msg, embed=em)
                    await asyncio.sleep(5)
                    await self.bot.delete_message(msg)
                    return False
            elif rep.reaction.emoji == "❔":
                await self.bot.clear_reactions(msg)
                em = discord.Embed(color=user.color, title="Ouvrir un compte Pay",
                                   description="Certaines fonctionnalités sur ce bot utilisent un système monétaire appelé"
                                               " ***Pay*** permettant par exemple de pouvoir participer à divers jeux.\n"
                                               "Il est important de savoir que cette monnaie est **virtuelle** et n'a "
                                               "donc aucune réelle valeur.\n"
                                               "A la création du compte, aucune information ne sera demandée.")
                em.set_footer(text="Veux-tu ouvrir un compte ?")
                info = await self.bot.edit_message(msg, embed=em)
                await self.bot.add_reaction(info, "✔")
                await self.bot.add_reaction(info, "✖")
                await asyncio.sleep(0.1)
                rep = await self.bot.wait_for_reaction(["✔", "✖"], message=info, timeout=20, check=check,
                                                       user=user)
                if rep is None or rep.reaction.emoji == "✖":
                    await self.bot.clear_reactions(msg)
                    em = discord.Embed(
                        description="{} ─ Annulé, vous pourrez en ouvrir un plus tard avec `.pay new`".format(
                            user.mention), color=palette["dark"])
                    await self.bot.edit_message(msg, embed=em)
                    await asyncio.sleep(8)
                    await self.bot.delete_message(msg)
                    return False
                elif rep.reaction.emoji == "✔":
                    if self.create_account(user):
                        await self.bot.clear_reactions(msg)
                        em = discord.Embed(
                            description="{} ─ Votre compte à été ouvert, vous pouvez désormais profiter des "
                                        "fonctionnalités économiques.".format(
                                user.mention), color=palette["lighter"])
                        await self.bot.edit_message(msg, embed=em)
                        return True
            await self.bot.say("**Erreur** ─ Je n'ai pas compris ...")
            return False
        return True


    def obj_transaction(self, trs: list):
        """Transforme les données brutes d'une transaction en tuple facile à exploiter"""
        """server_id = user_id = None
        for server in self.data:
            for user in self.data[server]["USERS"]:
                if trs in self.data[server]["USERS"][user]["logs"]:
                    server_id, user_id = server, user
        if server_id and user_id:
            server = self.bot.get_server(server_id)
            user = server.get_member(user_id)"""
        PayTrs = namedtuple('PayTrs', ['id', 'timestamp', 'somme', 'type', 'raison', 'link'])
        return PayTrs(trs[0], self.ttd(trs[1]), trs[3], trs[2], trs[4], trs[5])

    def get_transaction_metadata(self, trs_id: str):
        """Retrouve le membre et le serveur lié à une transaction"""
        server_id = user_id = None
        for server in self.data:
            for user in self.data[server]["USERS"]:
                if trs_id in [r[0] for r  in self.data[server]["USERS"][user]["logs"]]:
                    server_id, user_id = server, user
        if server_id and user_id:
            server = self.bot.get_server(server_id)
            user = server.get_member(user_id)
            return (server, user)
        return False

    def new_transaction(self, user: discord.Member, somme: int, type:str, raison: str):
        """Ajoute une transaction à un membre"""
        data = self.get_account(user)
        if data:
            timestamp = datetime.now().timestamp()
            trs_id = str(''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(5)))
            while self.get_transaction(trs_id):
                trs_id = str(
                    ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(5)))
            event = [trs_id, timestamp, type, somme, raison, []]
            data["logs"].append(event)
            if len(data["logs"]) > 30:
                data["logs"].remove(data["logs"][0])
            self.save()
            return self.obj_transaction(event)
        return False

    def link_transactions(self, trs_a, trs_b):
        a, b = self.get_transaction(trs_a, True), self.get_transaction(trs_b, True)
        if a and b:
            a[5].append(b[0])
            b[5].append(a[0])
            self.save()
            return True
        return False

    def get_transaction(self, trs_id: str, brut: bool = False):
        """Renvoie une transaction à partir de l'ID"""
        for serv in self.data:
            for user in self.data[serv]["USERS"]:
                for trs in self.data[serv]["USERS"][user]["logs"]:
                    if trs[0] == trs_id:
                        return self.obj_transaction(trs) if not brut else trs
        return False

    def get_transactions_from(self, user: discord.Member, nb: int = 1):
        """Renvoie les transactions d'un membre"""
        data = self.get_account(user, True)
        if data and nb >= 1:
            logs = data.logs[::-1]
            return logs[:nb]
        return False

    def daily_trs_from(self, user: discord.Member, jour: str = None):
        """Retourne les transactions d'un jour d'un membre"""
        if not jour:
            jour = time.strftime("%d/%m/%Y", time.localtime())
        data = self.get_account(user, True)
        if data:
            liste = []
            for t in data.logs:
                if t.timestamp.jour == jour:
                    liste.append([t.timestamp.float, t])
            sort = sorted(liste, key=operator.itemgetter(0), reverse=True)
            return [i[1] for i in sort]
        return False

    def daily_total_from(self, user: discord.member, jour: str = None):
        """Retourne la valeur totale de toutes les transactions d'un jour"""
        trs = self.daily_trs_from(user, jour)
        if trs:
            return sum([t.somme for t in trs])
        return 0


    def enough_credits(self, user: discord.Member, depense: int):
        """Vérifie que le membre peut réaliser cette transaction"""
        data = self.get_account(user, True)
        if data:
            return True if data.solde - depense >= 0 else False
        return False

    def add_credits(self, user: discord.Member, somme: int, raison: str):
        """Ajoute des crédits au membre"""
        data = self.get_account(user)
        if somme > 0:
            data["solde"] += somme
            return self.new_transaction(user, somme, "gain", raison)
        return False

    def remove_credits(self, user: discord.Member, somme: int, raison: str, accept_null: bool = False):
        """Retire des crédits à un membre"""
        somme = abs(somme)
        data = self.get_account(user)
        if self.enough_credits(user, somme):
            data["solde"] -= somme
            return self.new_transaction(user, -somme, "perte", raison)
        elif accept_null:
            somme = data["solde"]
            data["solde"] = 0
            return self.new_transaction(user, -somme, "perte", raison)
        return False

    def set_credits(self, user: discord.Member, somme: int, raison: str):
        """Modifie le solde du membre"""
        data = self.get_account(user)
        if somme >= 0:
            data["solde"] = somme
            return self.new_transaction(user, somme, "modification", raison)
        return False

    def transfert_credits(self, donneur: discord.Member, receveur: discord.Member, somme: int, raison: str):
        """Transfère les crédits d'un membre donneur à un membre receveur"""
        if donneur != receveur:
            if somme > 0:
                if self.enough_credits(donneur, somme):
                    don = self.remove_credits(donneur, somme, raison)
                    recu = self.add_credits(receveur, somme, raison)
                    self.link_transactions(don, recu)
                    return (don, recu)
        return False


    def total_credits_on_server(self, server: discord.Server):
        """Renvoie la valeur totale de la monnaie en circulation sur le serveur"""
        if server.id in self.data:
            return sum([user.solde for user in self.get_all_accounts(server)])
        return False

    def get_top(self, server: discord.Server, nombre: int):
        """Renvoie un top des plus riches du serveur"""
        if server.id in self.data:
            liste = [[u.solde, u] for u in self.get_all_accounts(server)]
            sort = sorted(liste, key=operator.itemgetter(0), reverse=True)
            return [i[1] for i in sort][:nombre]
        return False

    def get_top_usernum(self, user: discord.Member):
        """Renvoie la place du membre dans le top de son serveur"""
        server = user.server
        if server.id in self.data:
            liste = [[u.solde, u] for u in self.get_all_accounts(server)]
            sort = sorted(liste, key=operator.itemgetter(0), reverse=True)
            n = 1
            for i in sort:
                if i[1].userid == user.id:
                    return (n, i[1])
                n += 1
        return False

    def new_cooldown(self, user: discord.Member, id: str, duree: int):
        """Attribue un cooldown à un membre

        La durée est en secondes"""
        server = user.server
        fin = time.time() + duree
        if server.id not in self.cooldown:
            self.cooldown[server.id] = {}
        if id.lower() in self.cooldown[server.id]:
            if user.id in self.cooldown[server.id][id.lower()]:
                self.cooldown[server.id][id.lower()][user.id] += duree
            else:
                self.cooldown[server.id][id.lower()][user.id] = fin
        else:
            self.cooldown[server.id][id.lower()] = {user.id : fin}
        return self.cooldown[server.id][id.lower()][user.id]

    def get_cooldown(self, user: discord.Member, id: str):
        """Renvoie le cooldown du membre s'il y en a un"""
        server = user.server
        now = time.time()
        if server.id not in self.cooldown:
            self.cooldown[server.id] = {}
            return False
        if id.lower() not in self.cooldown[server.id]:
            return False
        if user.id in self.cooldown[server.id][id.lower()]:
            if now <= self.cooldown[server.id][id.lower()][user.id]:
                duree = int(self.cooldown[server.id][id.lower()][user.id] - now)
                return self.timeformat(duree)
            else:
                del self.cooldown[server.id][id.lower()][user.id]
                return False
        return False

    def reset_user(self, user: discord.Member):
        """Reset les données d'un membre"""
        server = user.server
        data = self.get_server(server, "USERS")
        if user.id in data:
            del data[user.id]
            self.save(True)
            return True
        return False

    def reset_all(self, server: discord.Server = None):
        """Reset toutes les données d'un serveur (ou tous les servs.)"""
        if server:
            self.get_server(server, reset=True)
            return True
        else:
            self.data = {}
            self.save(True)
            return True


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
        """Ensemble de commandes relatives au compte Turing Pay

        En absence de mention, renvoie les détails du compte de l'invocateur"""
        if ctx.invoked_subcommand is None:
            if not membre:
                membre = ctx.message.author
            await ctx.invoke(self.compte, user=membre)

    @pay_account.command(pass_context=True)
    async def new(self, ctx):
        """Ouvre un compte bancaire Pay"""
        data = self.pay.get_account(ctx.message.author)
        if data:
            await self.bot.say("**Inutile** ─ Vous avez déjà un compte : consultez-le avec `.b`")
        else:
            await self.pay.create_account(ctx.message.author)
            await self.bot.say("**Compte créé ─ Consultez-le avec `.b`")

    @pay_account.command(pass_context=True)
    async def compte(self, ctx, user: discord.Member = None):
        """Voir son compte Pay

        [user] -> Permet de voir le compte d'un autre membre"""
        user = user if user else ctx.message.author
        same = True if user == ctx.message.author else False
        server = ctx.message.server
        if same or self.pay.get_account(user):
            if await self.pay.account_dial(user):
                data = self.pay.get_account(user, True)
                gains = self.pay.daily_total_from(user)
                gainstxt = "+{}".format(gains) if gains >= 0 else "{}".format(gains)
                txt = "**Solde** ─ {} Gold{}\n" \
                      "**Aujourd'hui** ─ {}".format(data.solde, "s" if data.solde > 1 else "", gainstxt)
                em = discord.Embed(description=txt, color=user.color, timestamp=ctx.message.timestamp)
                em.set_author(name=user.name, icon_url=user.avatar_url)
                trs = self.pay.get_transactions_from(user, 3)
                if trs:
                    hist = ""
                    for i in trs:
                        if i.type == "modification":
                            somme = "=" + str(i.somme)
                        else:
                            somme = str(i.somme) if i.somme < 0 else "+" + str(i.somme)
                        raison = i.raison if len(i.raison) <= 40 else i.raison[:40] + "..."
                        hist += "**{}** ─ *{}* `{}`\n".format(somme, raison, i.id)
                    em.add_field(name="Historique", value=hist)
                await self.bot.say(embed=em)
            return
        await self.bot.say("**Inconnu** ─ *{}* ne possède pas de compte bancaire".format(user.name))

    @pay_account.command(pass_context=True)
    async def logs(self, ctx, user: discord.Member = None):
        """Affiche les dernières transactions du membre"""
        user = user if user else ctx.message.author
        data = self.pay.get_account(user, True)
        if data:
            txt = "Utilisez `.b check` pour voir une transaction en détails\n"
            page = 1
            jour = time.strftime("%d/%m/%Y", time.localtime())
            heure = time.strftime("%H:%M", time.localtime())
            for t in self.pay.get_transactions_from(user, 30):
                ts = t.timestamp.jour
                if t.timestamp.jour == jour:
                    if t.timestamp.heure == heure:
                        ts = "À l'instant"
                    else:
                        ts = t.timestamp.heure
                txt += "`{}` | {} ─ **{}** · *{}*\n".format(t.id, ts, t.somme, t.raison)
                if len(txt) > 1980 * page:
                    em = discord.Embed(title="Logs du compte de {}".format(user.name), description=txt,
                                       color=user.color, timestamp=ctx.message.timestamp)
                    em.set_footer(text="Page {}".format(page))
                    await self.bot.say(embed=em)
                    txt = ""
                    page += 1
            em = discord.Embed(title="Logs du compte de {}".format(user.name), description=txt,
                               color=user.color, timestamp=ctx.message.timestamp)
            em.set_footer(text="Page {}".format(page))
            await self.bot.say(embed=em)
        else:
            await self.bot.say("**Inconnu** ─ Aucun compte bancaire n'est lié à ce compte")

    @pay_account.command(pass_context=True)
    async def check(self, ctx, transaction_id: str):
        """Affiche les détails d'une transaction"""
        if len(transaction_id) == 5:
            trs = self.pay.get_transaction(transaction_id)
            if trs:
                details = self.pay.get_transaction_metadata(trs.id)
                somme = trs.somme
                if trs.type != "modification":
                    if trs.somme > 0:
                        somme = "+" + str(trs.somme)
                if trs.link:
                    link = " ".join(["`{}`".format(i) for i in trs.link])
                else:
                    link = "Aucune"
                txt = "*{}*\n\n" \
                      "**Type** ─ {}\n" \
                      "**Somme** ─ {}\n" \
                      "**Sur le compte de** ─ {}\n" \
                      "**Serveur** ─ {}\n" \
                      "**Transactions liées** ─ {}".format(trs.raison, trs.type.title(), somme,
                                                           details[1].name, details[0].name, link)
                em = discord.Embed(title="Relevé de transaction · {}".format(trs.id), description=txt, color=palette["stay"],
                                   timestamp=trs.timestamp.brut)
                await self.bot.say(embed=em)
            else:
                await self.bot.say("**Introuvable** ─ Mauvais identifiant ou transaction expirée")
        else:
            await self.bot.say("**Erreur** ─ L'identifiant est normalement composé de 5 caractères (chiffres et lettres)")


    @commands.command(pass_context=True, no_pm=True, aliases=["don"])
    async def give(self, ctx, receveur: discord.Member, somme: int, *raison):
        """Donner de l'argent à un autre membre"""
        server = ctx.message.server
        user = receveur
        raison = " ".join(raison) if raison else "Don de {} pour {}".format(ctx.message.author.name, user.name)
        if somme > 0:
            if self.pay.get_account(user):
                if await self.pay.account_dial(ctx.message.author):
                    if self.pay.enough_credits(ctx.message.author, somme):
                        cool = self.pay.get_cooldown(ctx.message.author, "give")
                        if not cool:
                            solde_before = self.pay.get_account(ctx.message.author, True).solde
                            if self.pay.transfert_credits(ctx.message.author, user, somme, raison):
                                prc = (somme / solde_before) * 100
                                ctime = 120 + (60 * round(prc))
                                self.pay.new_cooldown(ctx.message.author, "give", ctime)
                                await self.bot.say("**Transfert réalisé** ─ **{}**G ont été donnés à *{}*".format(somme, user.name))
                            else:
                                await self.bot.say("**Erreur** ─ La transaction n'a pas été réalisée correctement")
                        else:
                            await self.bot.say("**Cooldown** ─ Don possible dans `{}`".format(cool.string)) # MDR COOLSTRING
                    else:
                        await self.bot.say("**Crédits insuffisants** ─ ***{}*** vous n'avez pas cette somme, "
                                           "soyez raisonnable.".format(ctx.message.author.name))
                else:
                    await self.bot.say("Un compte Pay est nécessaire pour réaliser un don.")
            else:
                await self.bot.say("**Impossible** ─ Le membre cible n'a pas ouvert de compte")
        else:
            await self.bot.say("**Somme nulle ou négative** ─ Quels étaient tes projets ? Voler de l'argent ? (...)")

    @commands.command(pass_context=True, no_pm=True, aliases=["palmares"])
    async def top(self, ctx, top: int = 10):
        """Affiche un top des membres les plus riches du serveur"""
        server = ctx.message.server
        palm = self.pay.get_top(server, top)
        n = 1
        txt = ""
        found = False
        if palm:
            for l in palm:
                try:
                    username = server.get_member(l.userid).name
                except:
                    username = self.bot.get_user(l.userid).name
                if l.userid == ctx.message.author.id:
                    txt += "**{}.** __**{}**__ ─ **{}**G\n".format(n, username, l[0])
                    found = True
                else:
                    txt += "**{}.** **{}** ─ **{}**G\n".format(n, username, l[0])
                n += 1
            if not found:
                if self.pay.get_account(ctx.message.author):
                    place = self.pay.get_top_usernum(ctx.message.author)
                    txt += "(...)\n**{}.** **{}** ─ **{}**G".format(place[0], ctx.message.author.name, place[1].solde)
            em = discord.Embed(title="Top · Les plus riches du serveur", description=txt, color=palette["stay"], timestamp=ctx.message.timestamp)
            total = self.pay.total_credits_on_server(server)
            em.set_footer(text="Total = {} Golds".format(total))
            try:
                await self.bot.say(embed=em)
            except:
                await self.bot.say("**Erreur** ─ Le classement est trop long pour être envoyé")
        else:
            await self.bot.say("**Erreur** ─ Aucun membre n'a de compte sur ce serveur")

    @commands.command(pass_context=True, no_pm=True, aliases=["rj"])
    async def revenu(self, ctx):
        """Récupérer son revenu journalier"""
        user, server = ctx.message.author, ctx.message.server
        today = datetime.now().strftime("%d/%m/%Y")
        hier = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
        # Afin de pouvoir facilement modifier :
        base_rj = 100 # Revenu journalier de base
        base_jc = 20 # Bonus jours consécutifs
        if await self.pay.account_dial(user):
            data = self.pay.get_account(user)

            if "revenu" not in data["cache"]:
                data["cache"]["revenu"] = {"last": None, "suite": []}

            if today != data["cache"]["revenu"]["last"]:
                if data["cache"]["revenu"]["last"]:
                    then = datetime.strptime(data["cache"]["revenu"]["last"], "%d/%m/%Y")
                    delta_jour = (datetime.now() - then).days if (datetime.now() - then).days <= 7 else 7
                else:
                    delta_jour = 1
                data["cache"]["revenu"]["last"] = today

                if hier not in data["cache"]["revenu"]["suite"]:
                    data["cache"]["revenu"]["suite"] = [today]
                else:
                    if len(data["cache"]["revenu"]["suite"]) < 7:
                        data["cache"]["revenu"]["suite"].append(today)
                    else:
                        data["cache"]["revenu"]["suite"] = data["cache"]["revenu"]["suite"][1:]
                        data["cache"]["revenu"]["suite"].append(today)

                rj = base_rj * delta_jour
                savetxt = " (x{}j)".format(delta_jour) if delta_jour > 1 else ""
                bonusjc = (len(data["cache"]["revenu"]["suite"]) - 1) * base_jc
                if data["solde"] >= 50000:
                    bonusjc = 0
                    bonustxt = "\n• **Bonus** \"Jours consécutif\" ─ Non percevable (+ 50 000 G)"
                else:
                    bonustxt = "\n• **Bonus** \"Jours consécutif\" ─ **{}**G".format(bonusjc) if \
                        bonusjc > 0 else ""

                self.pay.add_credits(user, rj + bonusjc, "Revenus")
                notif = "• **Aide journalière** ─ **{}**G{}".format(rj, savetxt)
                notif += bonustxt

                em = discord.Embed(description=notif, color=user.color, timestamp=ctx.message.timestamp)
                em.set_author(name="Revenus", icon_url=user.avatar_url)
                em.set_footer(text="Solde actuel : {}G".format(data["solde"]))
                await self.bot.say(embed=em)
            else:
                await self.bot.say("**Refusé** ─ Tu as déjà pris ton revenu aujourd'hui.")
        else:
            await self.bot.say("**Refusé** ─ Un compte Pay est nécessaire afin de percevoir ces aides.")

    @commands.command(pass_context=True, aliases=["mas"])
    async def slot(self, ctx, offre: int = None):
        """Jouer à la machine à sous

        L'offre doit être comprise entre 10 et 500"""
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
        if not 10 <= offre <= 500:
            await self.bot.say("**Offre invalide** ─ Elle doit être comprise entre 10 et 500.")
            return
        base = offre
        if await self.pay.account_dial(user):
            if self.pay.enough_credits(user, offre):
                cool = self.pay.get_cooldown(user, "slot")
                if not cool:
                    self.pay.new_cooldown(user, "slot", 10)
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
                            offre *= 200
                            gaintxt = "3x ⚡ ─ Tu gagnes {} {}"
                        else:
                            offre = 0
                            gaintxt = "Tu t'es fait zap ⚡ ─ Tu perds ta mise !"
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
                    if base == 42: intro = "La réponse à la vie, l'univers et tout le reste"
                    if base == 28: intro = "Un nombre parfait pour jouer"
                    if base == 161: intro = "Le nombre d'or pour porter chance"
                    if base == 420: intro = "420BLAZEIT"
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
                        self.pay.add_credits(user, gain, "Gain à la machine à sous")
                        em = discord.Embed(title="Machine à sous ─ {}".format(user.name), description=disp,
                                           color=0x49ff6a)
                    else:
                        self.pay.remove_credits(user, base, "Perte à la machine à sous")
                        em = discord.Embed(title="Machine à sous ─ {}".format(user.name), description=disp,
                                           color=0xff4971)
                    em.set_footer(text=gaintxt.format(offre, "Golds"))
                    await self.bot.delete_message(msg)
                    await self.bot.say(embed=em)
                else:
                    await self.bot.say("**Cooldown** ─ Slot possible dans {}".format(cool.string))
            else:
                await self.bot.say("**Solde insuffisant** ─ Réduisez votre offre si possible")
        else:
            await self.bot.say("Un compte Pay est nécessaire pour jouer à la machine à sous.")


    @commands.group(name="modpay", aliases=["modbank", "mb"], pass_context=True, no_pm=True)
    @checks.admin_or_permissions(ban_members=True)
    async def _modpay(self, ctx):
        """Gestion de la banque pay"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_modpay.command(pass_context=True)
    async def forcenew(self, ctx, user: discord.Member):
        """Force l'ouverture du compte d'un membre"""
        if not self.pay.get_account(user):
            self.pay.create_account(user)
            await self.bot.say("**Succès** ─ Le compte bancaire de {} à été créé".format(user.mention))
        else:
            await self.bot.say("**Erreur** ─ Ce membre possède déjà un compte bancaire")

    @_modpay.command(pass_context=True)
    async def delete(self, ctx, user: discord.Member):
        """Supprime le compte bancaire d'un membre"""
        if self.pay.get_account(user):
            self.pay.reset_user(user)
            await self.bot.say("**Succès** ─ Le compte du membre a été effacé")
        else:
            await self.bot.say("**Erreur** ─ Le membre ne possède pas de compte bancaire")

    @_modpay.command(pass_context=True, hidden=True)
    async def resetall(self, ctx):
        """Reset les données du serveur, y compris la monnaie et les comptes bancaires des membres"""
        self.pay.reset_all(ctx.message.server)
        await self.bot.say("**Succès** ─ Toutes les données du serveur ont été reset")

    @_modpay.command(pass_context=True, hidden=True)
    @checks.is_owner()
    async def totalreset(self, ctx):
        """Reset les données des serveurs, y compris la monnaie et les comptes bancaires des membres"""
        self.pay.reset_all()
        await self.bot.say("**Succès** ─ Toutes les données de TOUS les serveurs ont été reset")

    @_modpay.command(pass_context=True)
    async def grant(self, ctx, user: discord.Member, somme: int, *raison):
        """Ajoute des crédits au compte d'un membre"""
        server = ctx.message.server
        raison = "Ajout par modération" if not raison else " ".join(raison)
        if somme > 0:
            if self.pay.get_account(user):
                self.pay.add_credits(user, somme, raison)
                await self.bot.say("**Succès** ─ {}G ont été donnés au membre".format(somme))
            else:
                await self.bot.say("**Erreur** ─ Le membre visé n'a pas de compte")
        else:
            await self.bot.say("**Erreur** ─ La somme doit être positive")

    @_modpay.command(pass_context=True)
    async def take(self, ctx, user: discord.Member, somme: int, *raison):
        """Retire des crédits à un membre"""
        server = ctx.message.server
        raison = "Retrait par modérateur" if not raison else " ".join(raison)
        if somme > 0:
            if self.pay.get_account(user):
                if not self.pay.enough_credits(user, somme):
                    somme = self.pay.get_account(user, True).solde
                self.pay.remove_credits(user, somme, raison)
                await self.bot.say("**Succès** ─ {}G ont été retirés au membre".format(somme))
            else:
                await self.bot.say("**Erreur** ─ Le membre visé n'a pas de compte")
        else:
            await self.bot.say("**Erreur** ─ La somme doit être positive")

    @_modpay.command(pass_context=True)
    async def set(self, ctx, user: discord.Member, somme: int, *raison):
        """Modifie le solde d'un membre"""
        server = ctx.message.server
        raison = "Modification par modération" if not raison else " ".join(raison)
        if somme >= 0:
            if self.pay.get_account(user):
                self.pay.set_credits(user, somme, raison)
                await self.bot.say("**Succès** ─ Le membre possède désormais {}G".format(somme))
            else:
                await self.bot.say("**Erreur** ─ Le membre visé n'a pas de compte")
        else:
            await self.bot.say("**Erreur** ─ La somme doit être positive ou nulle")

    @_modpay.command(name="import", pass_context=True, hidden=True)
    @checks.admin_or_permissions(administrator=True)
    async def user_import(self, ctx, user: discord.Member, base_solde: int):
        if not self.pay.get_account(user):
            self.pay.create_account(user)
        solde = (base_solde + 500) * 1.5
        self.pay.set_credits(user, int(solde), "Importation du compte v2")
        await self.bot.say("**Importé** ─ Le solde de {} a été rétabli".format(user.name))

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
