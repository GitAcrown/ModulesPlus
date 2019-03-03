import json
import os
import time

import apiai
import discord
import praw
from discord.ext import commands

from .utils.dataIO import fileIO, dataIO


class AwsmAPI:
    """API Awsm - Analyse du langage naturel"""
    def __init__(self, bot, path):
        self.bot = bot
        self.data = dataIO.load_json(path)
        self.meta = {"last_save": 0}

    def save(self, force: bool = False):
        if force:
            fileIO("data/awsm/data.json", "save", self.data)
        elif (time.time() - self.meta["last_save"]) >= 30: # 30s
            fileIO("data/awsm/data.json", "save", self.data)
            self.meta["last_save"] = time.time()

class Awsm:
    """Assistant personnel embarqué - Pour vous servir"""
    def __init__(self, bot):
        self.bot = bot
        self.ctr = AwsmAPI(bot, "data/awsm/data.json")
        self.sys = dataIO.load_json("data/awsm/sys.json")
        self.metasys = {"ls": 0}
        self.context = {}
        # Reddit PRAW
        self.reddit = praw.Reddit(client_id='uE7NMd2ISBWR7w', client_secret='2pZk2tj9oHMMz_BJCzbJd4JrIRY',
                     user_agent='discordbot:Stayawsm.:1.0 (by /u/Nordsko)')
        # DialogFlow
        self.CLIENT_TOKEN = "524242c7371f471aaf41aa5d306fc49d"
        self.dialog = apiai.ApiAI(self.CLIENT_TOKEN)

    def awsm_core(self, author = discord.Member):
        self.request = self.dialog.text_request()
        self.request.lang = "de"
        self.request.session_id = str(author.id)

    @commands.command(pass_context=True)
    async def fd(self, ctx):
        """Permet de discuter avec Awsm (TEST)"""
        self.awsm_core()
        content = ctx.message.content
        self.request.query = content
        try:
            rep = json.load(self.request.getresponse())["result"]["fulfillment"]["speech"]
            await self.bot.say(rep)
        except Exception as e:
            print(e)
            await self.bot.say("Désole je suis occupé...")


def check_folders():
    if not os.path.exists("data/awsm"):
        print("Creation du fichier Awsm ...")
        os.makedirs("data/awsm")


def check_files():
    if not os.path.isfile("data/awsm/data.json"):
        print("Création de awsm/data.json ...")
        fileIO("data/awsm/data.json", "save", {})

    if not os.path.isfile("data/awsm/sys.json"):
        print("Création de awsm/sys.json ...")
        fileIO("data/awsm/sys.json", "save", {})


def setup(bot):
    check_folders()
    check_files()
    n = Awsm(bot)
    bot.add_cog(n)
