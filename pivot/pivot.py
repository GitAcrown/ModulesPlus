import os
import random
import time

import discord
from cogs.utils.dataIO import fileIO, dataIO
from discord.ext import commands

from .utils import checks


class Pivot:
    """Outils de gestion d'une communauté"""
    def __init__(self, bot):
        self.bot = bot
        self.data = dataIO.load_json("data/pivot/data.json")

    def save(self):
        fileIO("data/pivot/data.json", "save", self.data)

    def get_server(self, server: discord.Server, reset: bool = False):
        if server.id not in self.data or reset:
            self.data[server.id] = {"teams": {}, # Va stocker l'historique des équipes de modos
                                    "resetid": int(time.time())} # Identifiant généré à chaque reset
            self.save()
        return self.data[server.id]

    def save_team(self, server: discord.Server, userlist, execut: discord.Member):
        """Sauvegarde une Team tirée au sort avec .modteam"""
        sys = self.get_server(server)
        nb = len(sys["teams"]) + 1
        sys["teams"][nb] = {"users": userlist,
                            "date": time.time(),
                            "executant": execut.id,
                            "num": nb}
        self.save()
        return sys["teams"][nb]


    @commands.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(administrator=True)
    async def modteam(self, ctx, nombre: int, *cibles):
        """Sélectionne <nombre> membres parmi la liste <cibles>

        La liste peut être une liste de membres ou un rôle qui liste déjà ces membres"""
        if ctx.message.mentions:
            cibles = ctx.message.mentions
        elif ctx.message.role_mentions:
            role = ctx.message.role_mentions[0].name
            cibles = [m for m in ctx.message.server.members if role in [i.name for i in m.roles]]
        else:
            await self.bot.say("❌ **Erreur** ─ Il me faut soit la liste des membres éligibles, "
                               "soit un rôle qui liste ces membres.")
            return
        if int(nombre) < len(cibles):
            sys = self.get_server(ctx.message.server)
            result = random.sample(cibles, nombre) # On tire X membres au hasard
            nb_team = len(sys["teams"]) + 1 # On récupère le numéro de cette nouvelle team

            rs = lambda: random.randint(0, 255)
            color = int('0x%02X%02X%02X' % (rs(), rs(), rs()), 16) # On génère une couleur unique pour chaque tirage

            teamtxt = ""
            ids = []
            for membre in result:
                teamtxt += "• {}\n".format(membre.mention)
                ids.append(membre.id)
            if self.save_team(ctx.message.server, ids, ctx.message.author):
                em = discord.Embed(title="Membres sélectionnés ─ Equipe n°{}".format(nb_team), description=teamtxt,
                                   color=color, timestamp=ctx.message.timestamp)
                em.set_footer(text="IDR: {}".format(sys["resetid"]))
                notif = await self.bot.say(embed=em)
                try:
                    accueil = [chan for chan in ctx.message.server.channels if chan.id == ctx.message.server.id][0]
                    if accueil != notif.channel:
                        await self.bot.send_message(accueil,
                                                    embed=em)  # On tente d'envoyer les résultats aussi sur le channel d'Accueil du serveur
                except:
                    pass
            else:
                await self.bot.say("**Erreur** ─ Impossible d'enregistrer l'équipe")
        else:
            await self.bot.say("**Refusé** ─ Le nombre à tirer au sort est supérieur ou égal au nombre de candidats")

    @commands.command(pass_context=True, no_pm=True)
    async def logsteam(self, ctx):
        """Affiche les équipes enregistrées en logs"""
        sys = self.get_server(ctx.message.server)
        em = discord.Embed(title="Logs d'équipes")
        em.set_footer(text="IDR = {}".format(sys["resetid"]))
        for team in sys["teams"]:
            membres = []
            for m in team["users"]:
                try:
                    membres.append(ctx.message.server.get_member(m).mention)
                except:
                    membres.append(m)
            txt = "**Membres** : {}\n".format(" ".join(membres))
            exec = ctx.message.server.get_member(team["executant"]).mention if \
                ctx.message.server.get_member(team["executant"]) else team["executant"]
            txt += "**Exécutant** : {}\n".format(exec)
            txt += "**Date** : {t.tm_mday}/{t.tm_mon}/{t.tm_year} à {t.tm_hour}:{t.tm_min}".format(
                t=time.localtime(team["date"]))
            em.add_field(name="Equipe n°{}".format(team["num"]), value=txt)
        await self.bot.say(embed=em)

    @commands.command(pass_context=True, no_pm=True)
    @checks.is_owner() # Seul le propriétaire du bot peut exécuter un reset
    async def resetpivot(self, ctx):
        """Reset les données serveur du module Pivot (teams etc.)"""
        sys = self.get_server(ctx.message.server, reset=True)
        await self.bot.say("Reset effectué pour `{}`. Nouvel IDR généré : **{}**".format(ctx.message.server.id,
                                                                                     sys["resetid"]))


def check_folders():
    if not os.path.exists("data/pivot"):
        print("Création du dossier Pivot...")
        os.makedirs("data/pivot")


def check_files():
    if not os.path.isfile("data/pivot/data.json"):
        print("Création de Pivot/data.json")
        dataIO.save_json("data/pivot/data.json", {})


def setup(bot):
    check_folders()
    check_files()
    n = Pivot(bot)
    bot.add_cog(n)