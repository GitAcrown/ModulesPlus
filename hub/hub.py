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

    def create_user(self, user, overwrite: bool = False):
        if user.id not in self.data or overwrite:
            self.data[user.id] = {"notifs": [],
                                  "subs": []}
            self.save()
        return self.data[user.id]

    def get_user(self, user):
        if user.id in self.data:
            return self.data[user.id]
        return {}

    def add_notif(self, user, sub: str, **kwargs):
        """Ajoute une notification à un membre"""
        data = self.get_user(user)
        if data:
            if sub in data["subs"]:
                kwargs["sub"] = sub
                data["notifs"].append(kwargs)
                return True
        return False

class Hub:
    """Gestionnaire du Hub personnel"""
    def __init__(self, bot):
        self.bot = bot
        self.hub = HubAPI(bot, "data/hub/data.json")
        self.daylock = {}

    def day_locked(self, user):
        """Vérifie que le membre n'a pas déjà été notifié aujourd'hui"""
        today = datetime.now().strftime("%d/%m/%Y")
        if user.id not in self.daylock:
            self.daylock[user.id] = ""
        if self.daylock[user.id] != today:
            self.daylock[user.id] = today
            return False
        return True

    async def send_notifs(self, user):
        """Récupère les notifications du membre et les envoie"""
        data = self.hub.get_user(user)
        if data:
            if data["notifs"]:
                for notif in data["notifs"]:
                    

    @commands.command(pass_context=True)
    async def reset_daylock(self, ctx):
        """Reset le bloquage quotidien des notifcations Hub"""
        await self.bot.say("**Reset effectué**")
        self.daylock = {}

    async def on_update(self, before, after):
        if after.id == "172376505354158080":
            if before.status == discord.Status.offline:
                if after.status in [discord.Status.online, discord.Status.idle, discord.Status.dnd]:
                    if not self.day_locked(after):
                        pass


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
