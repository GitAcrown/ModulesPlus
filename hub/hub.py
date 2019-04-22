import os
from datetime import datetime

import discord
from discord.ext import commands

from .utils import checks
from .utils.dataIO import fileIO, dataIO


class HubAPI:
    """API du Hub personnel"""
    def __init__(self, bot, path):
        self.bot = bot
        self.data = dataIO.load_json(path)

    def save(self):
        fileIO("data/hub/data.json", "save", self.data)

class Hub:
    """Gestionnaire du Hub personnel"""
    def __init__(self, bot):
        self.bot = bot
        self.hub = HubAPI(bot, "data/hub/data.json")
        self.cache = {}

    def can_interact(self, user):
        today = datetime.now().strftime("%d/%m/%Y")
        if user.id not in self.cache:
            self.cache[user.id] = ""
        if self.cache[user.id] != today:
            self.cache[user.id] = today
            return True
        return False

    @commands.command(pass_context=True)
    async def resethub(self, ctx):
        """Reset le compteur du hub"""
        await self.bot.say("**Reset effectué**")
        self.cache = {}

    async def on_update(self, before, after):
        if after.id == "172376505354158080":
            if before.status == discord.Status.offline:
                if after.status in [discord.Status.online, discord.Status.idle, discord.Status.dnd]:
                    if self.can_interact(after):
                        await self.bot.send_message(after, "Détecté")


def check_folders():
    if not os.path.exists("data/hub"):
        print("Creation du fichier hub ...")
        os.makedirs("data/hub")


def check_files():
    if not os.path.isfile("data/hub/data.json"):
        print("Création de hub/data.json ...")
        fileIO("data/hub/data.json", "save", {})


def setup(bot):
    check_folders()
    check_files()
    n = Hub(bot)
    bot.add_listener(n.on_update, "on_member_update")
    bot.add_cog(n)
