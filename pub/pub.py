import os
import random
import re
import string

import discord
from discord.ext import commands

from .utils import checks
from .utils.chat_formatting import pagify, box
from .utils.dataIO import dataIO


class Pub:
    """Commandes de publicité personnalisées"""

    def __init__(self, bot):
        self.bot = bot
        self.file_path = "data/pub/commands.json"
        self.c_commands = dataIO.load_json(self.file_path)

    @commands.group(pass_context=True, no_pm=True)
    async def pub(self, ctx):
        """Gestionnaire des commandes de Pub"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @pub.command(name="add", pass_context=True)
    @checks.mod_or_permissions(administrator=True)
    async def pub_add(self, ctx, command : str, *, text):
        """Ajoute une commande de publicité"""
        server = ctx.message.server
        command = command.lower()
        if command in self.bot.commands:
            await self.bot.say("Ce commande est déjà une commande standard.")
            return
        if server.id not in self.c_commands:
            self.c_commands[server.id] = {}
        couleur = int("".join([random.choice(string.digits + "abcdef") for _ in range(6)]), 16)
        cmdlist = self.c_commands[server.id]
        url = None
        reg = re.compile(r'(https?://(?:.*)/\w*\.[A-z]*)', re.DOTALL | re.IGNORECASE).findall(text)
        if reg:
            url = reg[0]
            text.replace(url, "")
        if command not in cmdlist:
            cmdlist[command] = {"contenu": text,
                                "image": url,
                                "color": couleur}
            self.c_commands[server.id] = cmdlist
            dataIO.save_json(self.file_path, self.c_commands)
            await self.bot.say("**Succès** ─ Commande ajoutée")
        else:
            await self.bot.say("**Impossible** ─ Cette commande existe déjà. Utilisez `.pub edit` pour la modifier.")

    @pub.command(name="edit", pass_context=True)
    @checks.mod_or_permissions(administrator=True)
    async def pub_edit(self, ctx, command : str, *, text):
        """Editer une commande de publicité"""
        server = ctx.message.server
        command = command.lower()
        if server.id in self.c_commands:
            cmdlist = self.c_commands[server.id]
            url = None
            reg = re.compile(r'(https?://(?:.*)/\w*\.[A-z]*)', re.DOTALL | re.IGNORECASE).findall(text)
            if reg:
                url = reg[0]
                text.replace(url, "")
            if command in cmdlist:
                cmdlist[command]["contenu"] = text
                cmdlist[command]["image"] = url
                self.c_commands[server.id] = cmdlist
                dataIO.save_json(self.file_path, self.c_commands)
                await self.bot.say("**Modifiée** ─ La commande a été modifiée avec succès.")
            else:
                await self.bot.say("**Inexistante** ─ Créez la commande avec `.pub new`")
        else:
            await self.bot.say("**Aucune commande** ─ Créez en une avec `.pub new`")

    @pub.command(name="delete", pass_context=True)
    @checks.mod_or_permissions(administrator=True)
    async def pub_delete(self, ctx, command : str):
        """Supprime une commande de publicité"""
        server = ctx.message.server
        command = command.lower()
        if server.id in self.c_commands:
            cmdlist = self.c_commands[server.id]
            if command in cmdlist:
                cmdlist.pop(command, None)
                self.c_commands[server.id] = cmdlist
                dataIO.save_json(self.file_path, self.c_commands)
                await self.bot.say("**Supprimée** ─ La commande a été supprimée avec succès.")
            else:
                await self.bot.say("**Inexistante** ─ Créez la commande avec `.pub new`")
        else:
            await self.bot.say("**Aucune commande** ─ Créez en une avec `.pub new`")

    @pub.command(name="list", pass_context=True)
    async def pub_list(self, ctx):
        """Affiche une liste des commandes personnalisées de publicité"""
        server = ctx.message.server
        commands = self.c_commands.get(server.id, {})

        if not commands:
            await self.bot.say("**Aucune commande** ─ Créez en une avec `.pub new`")
            return

        commands = ", ".join([ctx.prefix + c for c in sorted(commands)])
        commands = "Commandes personnalisées:\n\n" + commands

        if len(commands) < 1500:
            await self.bot.say(box(commands))
        else:
            for page in pagify(commands, delims=[" ", "\n"]):
                await self.bot.whisper(box(page))

    async def on_message(self, message):
        if len(message.content) < 2 or message.channel.is_private:
            return

        server = message.server
        prefix = self.get_prefix(message)

        if not prefix:
            return

        if server.id in self.c_commands and self.bot.user_allowed(message):
            cmdlist = self.c_commands[server.id]
            cmd = message.content[len(prefix):]
            if cmd in cmdlist:
                cmd = cmdlist[cmd]["contenu"]
                cmd = self.format_cc(cmd, message)
                color = cmdlist[cmd]["color"]
                image = cmdlist[cmd]["image"]
                cmd = self.format_cc(cmd, message)
                em = discord.Embed(description=cmd, color=color)
                em.set_image(url=image)
                await self.bot.send_message(message.channel, embed=em)
            elif cmd.lower() in cmdlist:
                cmd = cmdlist[cmd]["contenu"]
                color = cmdlist[cmd]["color"]
                image = cmdlist[cmd]["image"]
                cmd = self.format_cc(cmd, message)
                em = discord.Embed(description=cmd, color=color)
                em.set_image(url=image)
                await self.bot.send_message(message.channel, embed=em)

    def get_prefix(self, message):
        for p in self.bot.settings.get_prefixes(message.server):
            if message.content.startswith(p):
                return p
        return False

    def format_cc(self, command, message):
        results = re.findall("\{([^}]+)\}", command)
        for result in results:
            param = self.transform_parameter(result, message)
            command = command.replace("{" + result + "}", param)
        return command

    def transform_parameter(self, result, message):
        """
        For security reasons only specific objects are allowed
        Internals are ignored
        """
        raw_result = "{" + result + "}"
        objects = {
            "message" : message,
            "author"  : message.author,
            "channel" : message.channel,
            "server"  : message.server
        }
        if result in objects:
            return str(objects[result])
        try:
            first, second = result.split(".")
        except ValueError:
            return raw_result
        if first in objects and not second.startswith("_"):
            first = objects[first]
        else:
            return raw_result
        return str(getattr(first, second, raw_result))


def check_folders():
    if not os.path.exists("data/pub"):
        print("Creating data/pub folder...")
        os.makedirs("data/pub")


def check_files():
    f = "data/pub/commands.json"
    if not dataIO.is_valid_json(f):
        print("Creating empty commands.json...")
        dataIO.save_json(f, {})


def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(Pub(bot))