import os
import time

import apiai
import json
import praw
from discord.ext import commands

from .utils.dataIO import fileIO, dataIO


class FlowAPI:
    """API Flow - Analyse du langage naturel"""
    def __init__(self, bot, path):
        self.bot = bot
        self.data = dataIO.load_json(path)
        self.meta = {"last_save": 0}

    def save(self, force: bool = False):
        if force:
            fileIO("data/flow/data.json", "save", self.data)
        elif (time.time() - self.meta["last_save"]) >= 30: # 30s
            fileIO("data/flow/data.json", "save", self.data)
            self.meta["last_save"] = time.time()

class Flow:
    """Assistant personnel embarqué - Pour vous servir"""
    def __init__(self, bot):
        self.bot = bot
        self.ctr = FlowAPI(bot, "data/flow/data.json")
        self.sys = dataIO.load_json("data/flow/sys.json")
        self.metasys = {"ls": 0}
        self.context = {}
        self.reddit = praw.Reddit(client_id='uE7NMd2ISBWR7w',
                     client_secret='2pZk2tj9oHMMz_BJCzbJd4JrIRY',
                     user_agent='discordbot:Stayflow.:1.0 (by /u/Nordsko)')

    def coreflow(self):
        self.CLIENT_TOKEN = "bf8d293cce304d84835cddeea7d9947d"
        self.dialog = apiai.ApiAI(self.CLIENT_TOKEN)
        self.dialog_request = self.dialog.text_request()
        self.dialog_request.lang = "de"

    @commands.command(pass_context=True)
    async def fd(self, ctx):
        """Permet de discuter avec Flow (TEST)"""
        self.coreflow()
        content = ctx.message.content
        self.dialog_request.query(content)
        reponse = self.dialog_request.getresponse()
        obj = json.load(reponse)
        rep_dialog = obj["result"]["fulfillment"]["speech"]
        await self.bot.say(rep_dialog)

def check_folders():
    if not os.path.exists("data/flow"):
        print("Creation du fichier central ...")
        os.makedirs("data/flow")


def check_files():
    if not os.path.isfile("data/flow/data.json"):
        print("Création de flow/data.json ...")
        fileIO("data/flow/data.json", "save", {})

    if not os.path.isfile("data/flow/sys.json"):
        print("Création de flow/sys.json ...")
        fileIO("data/flow/sys.json", "save", {})


def setup(bot):
    check_folders()
    check_files()
    n = Flow(bot)
    bot.add_listener(n.on_msg, "on_message")
    bot.add_listener(n.on_reaction, "on_reaction_add")
    bot.add_cog(n)
