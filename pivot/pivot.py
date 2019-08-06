import os
import random
import time
import datetime

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
        return True

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
        em = discord.Embed(title="Logs d'équipes", inline=False)
        em.set_footer(text="IDR = {}".format(sys["resetid"]))
        for team in sys["teams"]:
            membres = []
            for m in sys["teams"][team]["users"]:
                try:
                    membres.append(ctx.message.server.get_member(m).mention)
                except:
                    membres.append(m)
            txt = "**Membres** : {}\n".format(" ".join(membres))
            exec = ctx.message.server.get_member(sys["teams"][team]["executant"]).mention if \
                ctx.message.server.get_member(sys["teams"][team]["executant"]) else sys["teams"][team]["executant"]
            txt += "**Exécutant** : {}\n".format(exec)
            txt += "**Date** : {t.tm_mday}/{t.tm_mon}/{t.tm_year} à {t.tm_hour}:{t.tm_min}".format(
                t=time.localtime(sys["teams"][team]["date"]))
            em.add_field(name="Equipe n°{}".format(sys["teams"][team]["num"]), value=txt)
        await self.bot.say(embed=em)

    @commands.command(pass_context=True, no_pm=True)
    @checks.is_owner() # Seul le propriétaire du bot peut exécuter un reset
    async def resetpivot(self, ctx):
        """Reset les données serveur du module Pivot (teams etc.)"""
        sys = self.get_server(ctx.message.server, reset=True)
        await self.bot.say("Reset effectué pour `{}`. Nouvel IDR généré : **{}**".format(ctx.message.server.id,
                                                                                     sys["resetid"]))

    @commands.command(pass_context=True, no_pm=True)
    @checks.is_owner()
    async def appendpivotteam(self, ctx, num: int):
        """Change le numero de la dernière team générée en cas de problème"""
        sys = self.get_server(ctx.message.server)
        nb = len(sys["teams"]) + 1
        sys["teams"][nb] = {"users": [ctx.message.author.id],
                            "date": time.time(),
                            "executant": ctx.message.author.id,
                            "num": nb}
        self.save()
        await self.bot.say("Ajout d'une team virtuelle avec succès")

    @commands.command(pass_context=True)
    async def screenshare(self, ctx, nom_salon: discord.Channel = None):
        """Génère un lien de partage d'écran pour un salon vocal sur le serveur"""
        if not nom_salon:
            if ctx.message.author.voice.voice_channel:
                nom_salon = ctx.message.author.voice.voice_channel
            else:
                await self.bot.say("Sélectionnez un salon vocal pour démarrer le partage d'écran ou rejoignez-en un avant de faire cette commande.")
                return
        if nom_salon.type == discord.ChannelType.voice:
            link = "https://www.discordapp.com/channels/{}/{}".format(nom_salon.server.id, nom_salon.id)
            txt = "1) Cliquez sur {}\n" \
                  "2) Si vous n'êtes pas déjà dans le salon vocal, cliquez sur le salon pour le rejoindre.\n" \
                  "3) Profitez.".format(nom_salon.mention)
            em = discord.Embed(title="Partage d'écran sur {}".format(nom_salon.name), description=txt, url=link, color=ctx.message.author.color)
            await self.bot.say(embed=em)
        else:
            await self.bot.say("Sélectionnez un salon vocal pour démarrer le partage d'écran ou rejoignez-en un avant de faire cette commande.")

    @commands.command(pass_context=True)
    async def mcompare(self, ctx, serverid_cible):
        """Compare les membres présents à la fois sur ce serveur et le serveur cible"""
        try:
            async def post(txt, page):
                em = discord.Embed(title="Membres présents sur {} et ici".format(server.name), description=txt)
                em.set_footer(text="Page {}".format(page))
                await self.bot.say(embed=em)
            txt = ""
            n = 1
            server = self.bot.get_server(serverid_cible)
            for m in server.members:
                if m in ctx.message.server.members:
                    txt += "{}\n".format(m.mention)
                    if len(txt) > 1970:
                        await post(txt, n)
                        n += 1
                        txt = ""
            await post(txt, n)
        except:
            await self.bot.say("Je ne suis pas sur le serveur cible, impossible d'y vérifier les membres.")


    async def citer(self, reaction, user):
        if reaction.message.channel:
            message = reaction.message
            if not user.bot:
                if reaction.emoji == "🗨":
                    msg_cite = "`" + "> **{}**\n".format(message.author.display_name)
                    clean_content = " ".join(message.content.split())
                    msg_cite += "> " + clean_content + "`"
                    try:
                        await self.bot.send_message(user, msg_cite)
                    except Exception as e:
                        print(e)

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
    bot.add_listener(n.citer, 'on_reaction_add')