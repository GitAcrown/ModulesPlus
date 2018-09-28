import asyncio
import os
import random
import time
from copy import deepcopy

import discord
from __main__ import send_cmd_help
from cogs.utils.dataIO import fileIO, dataIO
from discord.ext import commands

from .utils import checks


class Justice:
    """Module ajoutant des fonctionnalités avancées de modération"""
    def __init__(self, bot):
        self.bot = bot
        self.sys = dataIO.load_json("data/justice/sys.json")
        self.base_sys = {"PRISON_ROLE": "Prison", "PRISON_SALON": None, "HISTORIQUE": [], "SLOW": {},
                         "APPEL_SALON": None, "APPEL_USE": [], "FILTRE": {}, "GLOBALSLOW": False}
        self.reg = dataIO.load_json("data/justice/reg.json")
        self.slow_cooldown = {}
        self.globalslow_cooldown = {}

    def save(self):
        fileIO("data/justice/sys.json", "save", self.sys)
        fileIO("data/justice/reg.json", "save", self.reg)
        return True

    def convert_sec(self, form: str, val: int):
        if form == "j":
            return val * 86400
        elif form == "h":
            return val * 3600
        elif form == "m":
            return val * 60
        else:
            return val  # On considère alors que c'est déjà en secondes

    def add_event(self, user: discord.Member, type: str, temps: str = None, author: discord.Member = None):
        """Ajoute un event de la prison au serveur"""
        server = user.server
        if server.id not in self.sys:
            self.sys[server.id] = self.base_sys
        jour = time.strftime("%d/%m/%Y", time.localtime())
        heure = time.strftime("%H:%M", time.localtime())
        if type in ["+", "-", ">", "<", "!<", "x<", "r>"]:  # Ajout, Réduction, Entrée, Sortie, Sortie forcée, Sortie erreur, Retour en prison
            self.sys[server.id]["HISTORIQUE"].append([jour, heure, type, temps, user.id, author.id if author else None])
            self.save()
            return True
        else:
            return False

    @commands.group(name="modprison", aliases=["modjail", "mp"], pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def _modprison(self, ctx):
        """Paramètres de la Prison"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_modprison.command(pass_context=True)
    async def reset(self, ctx):
        """Reset totalement la prison et libère tous les membres"""
        server = ctx.message.server
        if server.id in self.reg:
            for u in self.reg[server.id]:
                self.reg[server.id][u]["TS_SORTIE"] = self.reg[server.id][u]["TS_ENTREE"] = 0
            self.save()
            await self.bot.say("**Reset** | Effectué avec succès, tous les membres ont été libérés.")
        else:
            await self.bot.say("**Inutile** | Le reset sur ce serveur est inutile.")

    @_modprison.command(pass_context=True, hidden=True)
    async def totalreset(self, ctx):
        """Reset la prison et les paramètres liés en les remettant aux options par défaut"""
        server = ctx.message.server
        if server.id in self.reg:
            for u in self.reg[server.id]:
                self.reg[server.id][u]["TS_SORTIE"] = self.reg[server.id][u]["TS_ENTREE"] = 0
        self.sys[server.id] = self.base_sys
        self.save()
        await self.bot.say("**Reset** | Effectué avec succès, tous les membres ont été libérés et les paramètres"
                           " ont été remis à leurs valeurs par défaut.")

    @_modprison.command(pass_context=True)
    async def salon(self, ctx, salon: discord.Channel):
        """Assigne la prison à un salon écrit"""
        server = ctx.message.server
        if server.id not in self.sys:
            self.sys[server.id] = self.base_sys
        self.sys[server.id]["PRISON_SALON"] = salon.id
        self.save()
        await self.bot.say("**Succès** | Le salon de prison est désormais {}\n"
                           "Vérifiez que les prisonniers n'aient accès qu'à ce salon.".format(salon.mention))

    @_modprison.command(pass_context=True)
    async def appelset(self, ctx, salon: discord.Channel = None):
        """Assigne un salon où recevoir les 'appels' - Si aucun salon n'est donné, désactive la fonctionnalité"""
        server = ctx.message.server
        if server.id not in self.sys:
            self.sys[server.id] = self.base_sys
        if "APPEL_SALON" not in self.sys[server.id]:
            self.sys[server.id]["APPEL_SALON"] = False
            self.sys[server.id]["APPEL_USE"] = []
        if salon:
            self.sys[server.id]["APPEL_SALON"] = salon.id
            await self.bot.say("**Succès** | Les messages d'appel seront envoyés sur le salon {}".format(salon.mention))
        else:
            self.sys[server.id]["APPEL_SALON"] = False
            await self.bot.say("**Désactivée** | Les prisonniers ne pourront plus envoyer un dernier message.")
        self.save()

    @_modprison.command(pass_context=True)
    async def role(self, ctx, role: discord.Role):
        """Assigne la prison à un salon écrit"""
        server = ctx.message.server
        if server.id not in self.sys:
            self.sys[server.id] = self.base_sys
        if role.name in [r.name for r in server.roles]:
            self.sys[server.id]["PRISON_ROLE"] = role.name
        self.save()
        await self.bot.say("**Succès** | Le rôle de prisonnier est désormais *{}*\n"
                           "Vérifiez que les permissions sur les salons soient corrects".format(role.name))

    @_modprison.command(pass_context=True)
    async def verifperms(self, ctx):
        """Vérifie les permissions des prisonniers et les corrige si besoin"""
        server = ctx.message.server
        if server.id not in self.sys:
            self.sys[server.id] = self.base_sys
        if self.sys[server.id]["PRISON_SALON"] and self.sys[server.id]["PRISON_ROLE"]:
            targets = ""
            role = discord.utils.get(server.roles, name=self.sys[server.id]["PRISON_ROLE"])
            for channel in server.channels:
                if channel.id != self.sys[server.id]["PRISON_SALON"]:
                    over = channel.overwrites_for(role)
                    if over.send_messages is True or over.send_messages is None:
                        targets += "- {} 🔄\n".format(channel.mention)
                        newover = discord.PermissionOverwrite()
                        newover.send_messages = False
                        await self.bot.edit_channel_permissions(channel, role, newover)
                    else:
                        targets += "- {} ✅\n".format(channel.mention)
            em = discord.Embed(title="Channels vérifiés", description=targets)
            em.set_footer(text="✅ = Permissions correctes | 🔄 = Permissions corrigées")
            await self.bot.say(embed=em)
        else:
            await self.bot.say("**Impossible** | Vous devez d'abord régler le rôle"
                               " `{0}mp role` et le channel de la prison `{0}mp salon`".format(ctx.prefix))

    @commands.group(name="filtre", aliases=["f"], pass_context=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def _filtre(self, ctx):
        """Commandes de filtre"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_filtre.command(pass_context=True)
    async def list(self, ctx, cible: discord.Member = None):
        """Affiche les mots filtrés pour le serveur ou si précisé, pour le membre ou le rôle visé"""
        server = ctx.message.server
        if server.id not in self.sys:
            self.sys[server.id] = self.base_sys
        if "FILTRE" not in self.sys[server.id]:
            self.sys[server.id]["FILTRE"] = {}
            self.save()
        if not cible:
            txt = ""
            for mot in self.sys[server.id]["FILTRE"]:
                users = [server.get_member(s) for s in self.sys[server.id]["FILTRE"][mot]["CIBLE_USER"]]
                roles = []
                for r in self.sys[server.id]["FILTRE"][mot]["CIBLE_ROLE"]:
                    role = discord.utils.get(server.roles, name=r)
                    roles.append(role)
                cibles = users + roles
                txt += "`{}` ─ {}\n".format(mot, ", ".join([s.name for s in cibles]))
            em = discord.Embed(title="Mots filtrés sur le serveur", description=txt if txt else "Aucun",
                               color=ctx.message.author.color)
            await self.bot.say(embed=em)
        else:
            if type(cible) is discord.Member:
                txt = ""
                for mot in self.sys[server.id]["FILTRE"]:
                    if cible.id in self.sys[server.id]["FILTRE"][mot]["CIBLE_USER"]:
                        txt += "`{}`\n".format(mot)
                em = discord.Embed(title="Mots filtrés pour {}".format(cible.name), description=txt if txt else "Aucun",
                                   color=ctx.message.author.color)
                await self.bot.say(embed=em)
            else:
                txt = ""
                for mot in self.sys[server.id]["FILTRE"]:
                    if cible.name in self.sys[server.id]["FILTRE"][mot]["CIBLE_ROLE"]:
                        txt += "`{}`\n".format(mot)
                em = discord.Embed(title="Mots filtrés pour {}".format(cible.name), description=txt,
                                   color=ctx.message.author.color)
                await self.bot.say(embed=em)

    @_filtre.command(pass_context=True)
    async def add(self, ctx, cible: discord.Member, texte: str, smartmode: bool = False):
        """Filtre un texte pour une cible (un mot unique)

        La cible peut être un membre en particulier ou un Rôle dans son ensemble
        Le Smartmode permet de filtrer aussi les mots proches (quand une lettre change par ex.)"""
        server = ctx.message.server
        if server.id not in self.sys:
            self.sys[server.id] = self.base_sys
        if "FILTRE" not in self.sys[server.id]:
            self.sys[server.id]["FILTRE"] = {}
            self.save()
        if smartmode:
            smt = " (+ Smartmode)"
        else:
            smt = ""
        if texte.lower() not in self.sys[server.id]["FILTRE"]:
            self.sys[server.id]["FILTRE"][texte.lower()] = {"SMART": smartmode,
                                                            "CIBLE_USER":
                                                                [cible.id] if type(cible) is discord.Member else [],
                                                            "CIBLE_ROLE":
                                                                [cible.name] if type(cible) is discord.Role else []}
            self.save()
            await self.bot.say("**Ajouté** | Le mot `{}` sera désormais filtré pour *{}*{}".format(texte.lower(),
                                                                                                 cible.name, smt))
        else:
            self.sys[server.id]["FILTRE"][texte.lower()]["SMART"] = smartmode
            if type(cible) is discord.Member:
                self.sys[server.id]["FILTRE"][texte.lower()]["CIBLE_USER"].append(cible.id)
                await self.bot.say("**Modifié** | Le mot `{}` sera aussi filtré pour *{}*{}".format(texte.lower(),
                                                                                                 cible.name, smt))
            else:
                self.sys[server.id]["FILTRE"][texte.lower()]["CIBLE_ROLE"].append(cible.name)
                await self.bot.say("**Modifié** | Le mot `{}` sera aussi filtré pour *{}*{}".format(texte.lower(),
                                                                                                 cible.name, smt))
            self.save()

    @_filtre.command(pass_context=True)
    async def remove(self, ctx, cible: discord.Member, texte: str):
        """Retire un filtre pour une cible"""
        server = ctx.message.server
        if server.id not in self.sys:
            self.sys[server.id] = self.base_sys
        if "FILTRE" not in self.sys[server.id]:
            self.sys[server.id]["FILTRE"] = {}
            self.save()
        if texte.lower() in self.sys[server.id]["FILTRE"]:
            if type(cible) is discord.Member:
                if cible.id in self.sys[server.id]["FILTRE"][texte.lower()]["CIBLE_USER"]:
                    self.sys[server.id]["FILTRE"][texte.lower()]["CIBLE_USER"].remove(cible.id)
                    await self.bot.say("**Retiré** | `{}` n'est plus filtré pour *{}*".format(texte.lower(), cible.name))
                else:
                    await self.bot.say("**Erreur** | Ce mot n'est pas filtré pour ce membre.")
            else:
                if cible.nom in self.sys[server.id]["FILTRE"][texte.lower()]["CIBLE_ROLE"]:
                    self.sys[server.id]["FILTRE"][texte.lower()]["CIBLE_ROLE"].remove(cible.nom)
                    await self.bot.say("**Retiré** | `{}` n'est plus filtré pour *{}*".format(texte.lower(), cible.name))
                else:
                    await self.bot.say("**Erreur** | Ce mot n'est pas filtré pour ce rôle.")
            if not self.sys[server.id]["FILTRE"][texte.lower()]["CIBLE_ROLE"] and not self.sys[server.id]["FILTRE"][
                texte.lower()]["CIBLE_USER"]:
                del self.sys[server.id]["FILTRE"][texte.lower()]
                await self.bot.say("**Filtre supprimé** | Il n'y a plus aucune cible.")
            self.save()
        else:
            await self.bot.say("**Erreur** | Ce texte n'est pas filtré")

    @_filtre.command(pass_context=True)
    async def delete(self, ctx, texte: str):
        """Supprime le filtre pour TOUTES LES CIBLES (Membres et rôles)"""
        server = ctx.message.server
        if server.id not in self.sys:
            self.sys[server.id] = self.base_sys
        if "FILTRE" not in self.sys[server.id]:
            self.sys[server.id]["FILTRE"] = {}
            self.save()
        if texte.lower() in self.sys[server.id]["FILTRE"]:
            del self.sys[server.id]["FILTRE"][texte.lower()]
            await self.bot.say("**Filtre supprimé** | Il n'y a plus aucune cible pour ce texte.")
            self.save()
        else:
            await self.bot.say("**Erreur** | Ce filtre n'existe pas.")

    @commands.command(aliases=["gs"], pass_context=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def globalslow(self, ctx, limite: int = 5):
        """Passe le serveur entier en mode Slow, limitant le nombre de messages par minute des membres"""
        server = ctx.message.server
        if server.id not in self.sys:
            self.sys[server.id] = self.base_sys
        if "GLOBALSLOW" not in self.sys[server.id]:
            self.sys[server.id]["GLOBALSLOW"] = False
            self.save()
        if self.sys[server.id]["GLOBALSLOW"]:
            self.sys[server.id]["GLOBALSLOW"] = False
            self.save()
            await self.bot.say("**Sortie du mode** | Les messages ne sont désormais plus limités.")
        else:
            self.sys[server.id]["GLOBALSLOW"] = limite
            self.save()
            await self.bot.say("**Entrée en mode Slow** | Les membres sont désormais limités à "
                               "**{}** msg/minute.".format(limite))

    @commands.command(aliases=["s"], pass_context=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def slow(self, ctx, user: discord.Member, limite: int = 5):
        """Passe un member en mode Slow, limitant son nombre de messages par minutes."""
        server = ctx.message.server
        if server.id not in self.sys:
            self.sys[server.id] = self.base_sys
        if "SLOW" not in self.sys[server.id]:
            self.sys[server.id]["SLOW"] = {}
            self.save()
        if user.id not in self.sys[server.id]["SLOW"]:
            self.sys[server.id]["SLOW"][user.id] = limite
            self.save()
            em = discord.Embed(description="**Slow** | {} est désormais limité à {} messages par minute.".format(
                user.mention, limite), color=ctx.message.author.color)
            msg = await self.bot.say(embed=em)
            await self.bot.send_message(user, "**Slow** | Vous êtes désormais limité à {} messages par minute (par {})"
                                              "".format(limite, ctx.message.author.mention))
            await asyncio.sleep(6)
            await self.bot.delete_message(msg)
        else:
            del self.sys[server.id]["SLOW"][user.id]
            self.save()
            em = discord.Embed(description="**Slow** | {} n'est plus limité.".format(
                user.mention), color=ctx.message.author.color)
            msg = await self.bot.say(embed=em)
            await self.bot.send_message(user, "**Slow** | Vous avez été sorti du mode (par {})"
                                              "".format(ctx.message.author.mention))
            await asyncio.sleep(6)
            await self.bot.delete_message(msg)

    @commands.command(pass_context=True)
    async def appel(self, ctx, *message: str):
        """Permet d'envoyer un unique message après votre mise en prison"""
        author = ctx.message.author
        server = ctx.message.server
        if self.sys[server.id]["APPEL_SALON"]:
            salon = self.bot.get_channel(self.sys[server.id]["APPEL_SALON"])
            message = " ".join(message)
            if author.id in self.sys[server.id]["APPEL_USE"]:
                if len(message) > 300:
                    await self.bot.say("**Trop long** | Ce message est limité à 300 caractères, pas un de plus.")
                    return
                em = discord.Embed(color=author.color, description="*{}*".format(message))
                em.set_author(name="Appel de {}".format(str(author)), icon_url=author.avatar_url)
                em.set_footer(text="Ce message unique à été envoyé depuis la prison où {} est enfermé·e.".format(
                    author.name))
                await self.bot.send_typing(salon)
                await asyncio.sleep(1)
                if author.id in self.sys[server.id]["APPEL_USE"]:
                    self.sys[server.id]["APPEL_USE"].remove(author.id)
                await self.bot.send_message(salon, embed=em)
                self.save()
                await self.bot.say("**Votre message à été envoyé avec succès**")
            else:
                await self.bot.say("**Refusé** | Vous n'y avez pas le droit.")

    @commands.command(aliases=["ph"], pass_context=True)
    async def historique(self, ctx, nb: int = 10):
        """Voir l'historique de la prison sur ce serveur

        Types:
        > Entrée
        r> Retour en prison
        V> Visite de la prison
        < Sortie
        x< Erreur sortie
        !< Sortie par modérateur
        + Ajout de temps
        - Réduction de temps"""
        server = ctx.message.server
        today = time.strftime("%d/%m/%Y", time.localtime())
        if server.id not in self.sys:
            self.sys[server.id] = self.base_sys
        if self.sys[server.id]["HISTORIQUE"]:
            b = self.sys[server.id]["HISTORIQUE"][-nb:]
            txt = ""
            b.reverse()
            for e in b:
                temps = e[3] + " " if e[3] else ""
                auteur = " (par <@{}>)".format(e[5]) if e[5] else ""
                user = server.get_member(e[4])
                if e[0] == today:
                    txt += "**{}** **{}** {}<@{}>{}\n".format(e[1], e[2], temps, user.id, auteur)
                else:
                    txt += "**{}** **{}** {}<@{}>{}\n".format(e[0], e[2], temps, user.id, auteur)
            em = discord.Embed(title="Historique de la Prison", description=txt)
            em.set_footer(text="Historique du serveur {}".format(server.name))
            await self.bot.say(embed=em)
        else:
            await self.bot.say("**Vide** | La prison n'a enregistré aucune action sur ce serveur.")

    @commands.command(aliases=["pl"], pass_context=True)
    async def prisonliste(self, ctx, bot_slmt: bool = True):
        """Liste les membres en prison

        <bot_slmt> = Si FALSE, affiche les membres qui n'ont pas été emprisonnés via le bot"""
        server = ctx.message.server
        if server.id not in self.sys:
            self.sys[server.id] = self.base_sys
        if server.id not in self.reg:
            self.reg[server.id] = {}
            await self.bot.say("**Vide** | Aucun membre n'est emprisonné en ce moment même.")
            self.save()
            return
        txt = ""
        al = []
        for u in self.reg[server.id]:
            if self.reg[server.id][u]["TS_SORTIE"] >= time.time():
                al.append(u)
                user = server.get_member(u)
                estim = time.strftime("%H:%M", time.localtime(self.reg[server.id][u]["TS_SORTIE"]))
                vtxt = ""
                if "VISITE" in self.reg[server.id][u]:
                    if self.reg[server.id][u]["VISITE"]:
                        vtxt = " (En visite)"
                mention = user.mention if user else "<@{}>".format(u)
                txt += "{} ─ Sortie à `{}`{}\n".format(mention, estim, vtxt)

        if not bot_slmt:
            for member in server.members:
                if self.sys[server.id]["PRISON_ROLE"] in [r.name for r in member.roles]:
                    if member.id not in al:
                        txt += "{} ─ Heure de sortie inconnue\n".format(member.mention)
        if txt == "":
            await self.bot.say("**Vide** | Aucun membre n'est emprisonné en ce moment même.")
            return
        em = discord.Embed(title="Prisonniers", description=txt)
        em.set_footer(text="Sur le serveur {}".format(server.name))
        await self.bot.say(embed=em)

    @commands.command(aliases=["p", "jail"], pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def prison(self, ctx, user: discord.Member, temps: str = "10m"):
        """Emprisonner un membre pendant un certain temps (Défaut = 10m)

        <user> = Membre à emprisonner
        <temps> = Valeur suivie de l'unité (m, h ou j)
        -- Il est possible d'ajouter devant la valeur de temps '+' et '-' pour moduler une peine"""
        message = ctx.message
        today = time.strftime("%d/%m", time.localtime())
        server = message.server
        form = temps[-1:]  # C'est le format du temps (smhj)
        if form not in ["s", "m", "h", "j"]:
            await self.bot.whisper("**Unités** | `m` = Minutes, `h` = Heures, `j` = Jours\n"
                                   "Exemple: `{}p @membre 5h`".format(ctx.prefix))
            return
        if server.id not in self.sys:
            self.sys[server.id] = self.base_sys
        if server.id not in self.reg:
            self.reg[server.id] = {}
        if "APPEL_SALON" not in self.sys[server.id]:
            self.sys[server.id]["APPEL_SALON"] = False
            self.sys[server.id]["APPEL_USE"] = []
        appel = True if self.sys[server.id]["APPEL_SALON"] else False
        role = self.sys[server.id]["PRISON_ROLE"]
        prisonchan = self.bot.get_channel(self.sys[server.id]["PRISON_SALON"]).name if \
            self.sys[server.id]["PRISON_SALON"] else False
        try:
            apply = discord.utils.get(message.server.roles, name=role)  # Objet: Rôle
        except:
            await self.bot.say("**Erreur** | Le rôle *{}* n'est pas présent sur ce serveur.".format(role))
            return

        if temps.startswith("+") or temps.startswith("-"):  # Ajouter ou retirer du temps de prison
            val = temps.replace(form, "")
            val = int(val.replace(temps[0], ""))
            if user.id in self.reg[server.id]:
                if role in [r.name for r in user.roles]:
                    modif = self.convert_sec(form, val)
                    if temps[0] == "+":
                        self.reg[server.id][user.id]["TS_SORTIE"] += modif
                        estim = time.strftime("%H:%M", time.localtime(self.reg[server.id][user.id]["TS_SORTIE"]))
                        estimdate = time.strftime("%d/%m", time.localtime(self.reg[server.id][user.id]["TS_SORTIE"]))
                        msg = "{} ─ Ajout de **{}{}** de peine".format(user.mention, val, form)
                        if estimdate == today:
                            estim_txt = "Sortie estimée à {}".format(estim)
                        else:
                            estim_txt = "Sortie estimée le {} à {}".format(estimdate, estim)
                        self.add_event(user, "+", "{}{}".format(val, form), author=ctx.message.author)

                        em = discord.Embed(description=msg, color=apply.color)
                        em.set_footer(text=estim_txt)
                        notif = await self.bot.say(embed=em)
                        await asyncio.sleep(7)
                        await self.bot.delete_message(notif)

                        em = discord.Embed(description="**Peine augmentée** ─ **+{}{}** par *{}*".format(
                            val, form, ctx.message.author.name), color=apply.color)
                        if estimdate == today:
                            em.set_footer(text="Sortie prévue à {}".format(estim))
                        else:
                            em.set_footer(text="Sortie prévue le {} à {}".format(estimdate, estim))
                        try:
                            await self.bot.send_message(user, embed=em)
                        except:
                            if prisonchan:
                                await self.bot.send_message(prisonchan, embed=em)
                    elif temps[0] == "-":
                        self.reg[server.id][user.id]["TS_SORTIE"] -= modif
                        if self.reg[server.id][user.id]["TS_SORTIE"] < time.time():
                            estim = time.strftime("%H:%M", time.localtime())
                            estimdate = time.strftime("%d/%m", time.localtime())
                        else:
                            estim = time.strftime("%H:%M", time.localtime(self.reg[server.id][user.id]["TS_SORTIE"]))
                            estimdate = time.strftime("%d/%m", time.localtime(self.reg[server.id][user.id]["TS_SORTIE"]))
                        msg = "{} ─ Réduction de **{}{}** de peine".format(user.mention, val, form)
                        if estimdate == today:
                            estim_txt = "Sortie estimée à {}".format(estim)
                        else:
                            estim_txt = "Sortie estimée le {} à {}".format(estimdate, estim)
                        self.add_event(user, "-", "{}{}".format(val, form), author=ctx.message.author)

                        em = discord.Embed(description=msg, color=apply.color)
                        em.set_footer(text=estim_txt)
                        notif = await self.bot.say(embed=em)
                        await asyncio.sleep(7)
                        await self.bot.delete_message(notif)

                        em = discord.Embed(description="**Peine réduite** ─ **-{}{}** par *{}*".format(
                            val, form, ctx.message.author.name), color=apply.color)
                        if estimdate == today:
                            em.set_footer(text="Sortie prévue à {}".format(estim))
                        else:
                            em.set_footer(text="Sortie prévue le {} à {}".format(estimdate, estim))
                        try:
                            await self.bot.send_message(user, embed=em)
                        except:
                            if prisonchan:
                                await self.bot.send_message(self.bot.get_channel(self.sys[server.id]["PRISON_SALON"]), embed=em)
                    else:
                        await self.bot.say("**Symbole non reconnu** | `+` = Ajouter / `-` = Réduire")
                        return
                else:
                    if temps[0] == "+":
                        new_message = deepcopy(message)
                        new_message.content = ctx.prefix + "p {} {}".format(user.mention, temps.replace("+", ""))
                        await self.bot.process_commands(new_message)
                    else:
                        await self.bot.say("**Erreur** | Le membre n'est pas en prison (Absence de rôle)")
                        return
            else:
                if temps[0] == "+":
                    new_message = deepcopy(message)
                    new_message.content = ctx.prefix + "p {} {}".format(user.mention, temps.replace("+", ""))
                    await self.bot.process_commands(new_message)
                else:
                    await self.bot.say("**Erreur** | Le membre n'est pas en prison (Non-enregistré)")
                    return
        else:
            val = int(temps.replace(form, ""))
            sec = self.convert_sec(form, val)
            n = 0
            if sec < 60:
                sec = 60 # Au moins une minute
            if sec > 86400:
                notif = await self.bot.say("**Attention** | "
                                           "Une telle durée peut causer une peine infinie à la moindre instabilité")
                await asyncio.sleep(3)
                await self.bot.delete_message(notif)
            if user.id not in self.reg[server.id]:
                self.reg[server.id][user.id] = {"TS_ENTREE": 0,
                                                "TS_SORTIE": 0,
                                                "CASIER": [],
                                                "VISITE": False}
            if role not in [r.name for r in user.roles]:
                b_peine = time.time()
                self.reg[server.id][user.id]["TS_ENTREE"] = b_peine
                self.reg[server.id][user.id]["TS_SORTIE"] = b_peine + sec
                await self.bot.add_roles(user, apply)
                if appel and user.id not in self.sys[server.id]["APPEL_USE"]:
                    self.sys[server.id]["APPEL_USE"].append(user.id)
                msg = "{} ─ Mise en prison pour **{}{}**".format(user.mention, val, form)
                estim = time.strftime("%H:%M", time.localtime(self.reg[server.id][user.id]["TS_SORTIE"]))
                estimdate = time.strftime("%d/%m", time.localtime(self.reg[server.id][user.id]["TS_SORTIE"]))
                if estimdate == today:
                    estim_txt = "Sortie estimée à {}".format(estim)
                else:
                    estim_txt = "Sortie estimée le {} à {}".format(estimdate, estim)
                self.add_event(user, ">", "{}{}".format(val, form), author=ctx.message.author)
                if prisonchan:
                    txt = "\nVous avez accès au salon *{}* pour toute réclamation".format(prisonchan)
                else:
                    txt = ""
                if appel:
                    txt += "\n─ Vous avez le droit d'envoyer un dernier message avec `{}appel`".format(ctx.prefix)
                em = discord.Embed(description="**Peine de prison** ─ **{}{}** par *{}*{}".format(
                    val, form, ctx.message.author.name, txt), color=apply.color)
                if estimdate == today:
                    em.set_footer(text="Sortie prévue à {}".format(estim))
                else:
                    em.set_footer(text="Sortie prévue le {} à {}".format(estimdate, estim))
                try:
                    await self.bot.send_message(user, embed=em)
                except:
                    if prisonchan:
                        await self.bot.send_message(self.bot.get_channel(self.sys[server.id]["PRISON_SALON"]), "{}".format(user.mention))
                        await self.bot.send_message(self.bot.get_channel(self.sys[server.id]["PRISON_SALON"]), embed=em)

                em = discord.Embed(description=msg, color=apply.color)
                em.set_footer(text=estim_txt)
                notif = await self.bot.say(embed=em)
                await asyncio.sleep(7)
                await self.bot.delete_message(notif)

                self.save()
                while time.time() < self.reg[server.id][user.id]["TS_SORTIE"]:
                    await asyncio.sleep(1)  # TIMER ============#

                if user in server.members:
                    if role in [r.name for r in user.roles]:
                        self.reg[server.id][user.id]["TS_ENTREE"] = self.reg[server.id][user.id]["TS_SORTIE"] = 0
                        self.add_event(user, "<")
                        await self.bot.remove_roles(user, apply)
                        if user.id in self.sys[server.id]["APPEL_USE"] and appel:
                            self.sys[server.id]["APPEL_USE"].remove(user.id)
                        em = discord.Embed(description="**Peine de prison** ─ Vous êtes désormais libre",
                                           color=apply.color)
                        try:
                            await self.bot.send_message(user, embed=em)
                        except:
                            if prisonchan:
                                await self.bot.send_message(self.bot.get_channel(self.sys[server.id]["PRISON_SALON"]), "{}".format(user.mention))
                                await self.bot.send_message(self.bot.get_channel(self.sys[server.id]["PRISON_SALON"]), embed=em)
                        rand = random.choice(["est désormais libre", "regagne sa liberté", "est sorti de prison",
                                              "profite à nouveau de l'air frais"])
                        em = discord.Embed(description="{} {}".format(user.mention, rand), color=apply.color)
                        notif = await self.bot.say(embed=em)
                        await asyncio.sleep(7)
                        await self.bot.delete_message(notif)
                    else:
                        return
                else:
                    em = discord.Embed(description="**Sortie de** <@{}> | Il n'est plus sur le serveur.")
                    if user.id in self.sys[server.id]["APPEL_USE"] and appel:
                        self.sys[server.id]["APPEL_USE"].remove(user.id)
                    self.add_event(user, "x<")
                    notif = await self.bot.say(embed=em)
                    await asyncio.sleep(5)
                    await self.bot.delete_message(notif)
            else:
                self.reg[server.id][user.id]["TS_ENTREE"] = self.reg[server.id][user.id]["TS_SORTIE"] = 0
                await self.bot.remove_roles(user, apply)
                if user.id in self.sys[server.id]["APPEL_USE"] and appel:
                    self.sys[server.id]["APPEL_USE"].remove(user.id)
                self.add_event(user, "!<", author=ctx.message.author)
                em = discord.Embed(description="{} a été libéré par {}".format(
                    user.mention, ctx.message.author.mention), color=apply.color)
                notif = await self.bot.say(embed=em)
                em = discord.Embed(description="**Peine de prison** ─ Vous êtes désormais libre", color=apply.color)
                try:
                    await self.bot.send_message(user, embed=em)
                except:
                    if prisonchan:
                        await self.bot.send_message(self.bot.get_channel(self.sys[server.id]["PRISON_SALON"]), "{}".format(user.mention))
                        await self.bot.send_message(self.bot.get_channel(self.sys[server.id]["PRISON_SALON"]), embed=em)
                await asyncio.sleep(7)
                await self.bot.delete_message(notif)

    @commands.command(aliases=["vp"], pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def visite(self, ctx, user: discord.Member = None):
        """Permet de visiter la prison pendant 10 minutes

        [user] = Membre à emprisonner pour la visite si ce n'est pas vous-même"""
        message = ctx.message
        if user is None:
            user = ctx.message.author
        server = message.server
        today = time.strftime("%d/%m", time.localtime())
        temps = "10m"
        form = temps[-1:]  # C'est le format du temps (smhj)
        if form not in ["s", "m", "h", "j"]:
            await self.bot.whisper("**Unités** | `m` = Minutes, `h` = Heures, `j` = Jours\n"
                                   "Exemple: `{}p @membre 5h`".format(ctx.prefix))
            return
        if server.id not in self.sys:
            self.sys[server.id] = self.base_sys
        if server.id not in self.reg:
            self.reg[server.id] = {}
        if "APPEL_SALON" not in self.sys[server.id]:
            self.sys[server.id]["APPEL_SALON"] = False
            self.sys[server.id]["APPEL_USE"] = []
        appel = True if self.sys[server.id]["APPEL_SALON"] else False
        role = self.sys[server.id]["PRISON_ROLE"]
        prisonchan = self.bot.get_channel(self.sys[server.id]["PRISON_SALON"]).name if \
            self.sys[server.id]["PRISON_SALON"] else False
        try:
            apply = discord.utils.get(message.server.roles, name=role)  # Objet: Rôle
        except:
            await self.bot.say("**Erreur** | Le rôle *{}* n'est pas présent sur ce serveur.".format(role))
            return

        val = int(temps.replace(form, ""))
        sec = self.convert_sec(form, val)
        n = 0
        if user.id not in self.reg[server.id]:
            self.reg[server.id][user.id] = {"TS_ENTREE": 0,
                                            "TS_SORTIE": 0,
                                            "CASIER": [],
                                            "VISITE": False}
        if "VISITE" not in self.reg[server.id][user.id]:
            self.reg[server.id][user.id]["VISITE"] = False
        if role not in [r.name for r in user.roles]:
            b_peine = time.time()
            self.reg[server.id][user.id]["VISITE"] = True
            self.reg[server.id][user.id]["TS_ENTREE"] = b_peine
            self.reg[server.id][user.id]["TS_SORTIE"] = b_peine + sec
            await self.bot.add_roles(user, apply)
            if appel and user.id not in self.sys[server.id]["APPEL_USE"]:
                self.sys[server.id]["APPEL_USE"].append(user.id)
            msg = "{} ─ Visite de la prison (10 minutes)".format(user.mention)
            estim = time.strftime("%H:%M", time.localtime(self.reg[server.id][user.id]["TS_SORTIE"]))
            estimdate = time.strftime("%d/%m", time.localtime(self.reg[server.id][user.id]["TS_SORTIE"]))
            if estimdate == today:
                estim_txt = "Sortie estimée à {}".format(estim)
            else:
                estim_txt = "Sortie estimée le {} à {}".format(estimdate, estim)
            self.add_event(user, "V>", "{}{}".format(val, form), author=ctx.message.author)
            em = discord.Embed(description="**Visite de la prison** ─ 10 minutes", color=apply.color)
            if estimdate == today:
                em.set_footer(text="Sortie prévue à {}".format(estim))
            else:
                em.set_footer(text="Sortie prévue le {} à {}".format(estimdate, estim))
            try:
                await self.bot.send_message(user, embed=em)
            except:
                if prisonchan:
                    await self.bot.send_message(prisonchan, "{}".format(user.mention))
                    await self.bot.send_message(prisonchan, embed=em)

            em = discord.Embed(description=msg, color=apply.color)
            em.set_footer(text=estim_txt)
            notif = await self.bot.say(embed=em)
            await asyncio.sleep(6)
            await self.bot.delete_message(notif)

            self.save()
            while time.time() < self.reg[server.id][user.id]["TS_SORTIE"]:
                await asyncio.sleep(1)  # TIMER ============#

            if user in server.members:
                if role in [r.name for r in user.roles]:
                    self.reg[server.id][user.id]["TS_ENTREE"] = self.reg[server.id][user.id]["TS_SORTIE"] = 0
                    self.reg[server.id][user.id]["VISITE"] = False
                    self.add_event(user, "<")
                    await self.bot.remove_roles(user, apply)
                    if user.id in self.sys[server.id]["APPEL_USE"] and appel:
                        self.sys[server.id]["APPEL_USE"].remove(user.id)
                    em = discord.Embed(description="**Visite de la prison** ─ Votre visite est terminée !",
                                       color=apply.color)
                    try:
                        await self.bot.send_message(user, embed=em)
                    except:
                        if prisonchan:
                            await self.bot.send_message(prisonchan, "{}".format(user.mention))
                            await self.bot.send_message(prisonchan, embed=em)
                    rand = random.choice(["a terminé sa visite", "regagne sa liberté"])
                    em = discord.Embed(description="{} {}".format(user.mention, rand), color=apply.color)
                    notif = await self.bot.say(embed=em)
                    await asyncio.sleep(6)
                    await self.bot.delete_message(notif)
                else:
                    return
            else:
                em = discord.Embed(description="**Fin de visite de ** <@{}> | Ce membre n'est plus sur le serveur.")
                if user.id in self.sys[server.id]["APPEL_USE"] and appel:
                    self.sys[server.id]["APPEL_USE"].remove(user.id)
                self.add_event(user, "x<")
                notif = await self.bot.say(embed=em)
                await asyncio.sleep(5)
                await self.bot.delete_message(notif)
        else:
            self.reg[server.id][user.id]["TS_ENTREE"] = self.reg[server.id][user.id]["TS_SORTIE"] = 0
            self.reg[server.id][user.id]["VISITE"] = False
            await self.bot.remove_roles(user, apply)
            if user.id in self.sys[server.id]["APPEL_USE"] and appel:
                self.sys[server.id]["APPEL_USE"].remove(user.id)
            self.add_event(user, "!<", author=ctx.message.author)
            em = discord.Embed(description="{} a été sorti.e par {}".format(
                user.mention, ctx.message.author.mention), color=apply.color)
            notif = await self.bot.say(embed=em)
            em = discord.Embed(description="**Visite de la prison** ─ On vous a sorti plus tôt", color=apply.color)
            try:
                await self.bot.send_message(user, embed=em)
            except:
                if prisonchan:
                    await self.bot.send_message(prisonchan, "{}".format(user.mention))
                    await self.bot.send_message(prisonchan, embed=em)
            await asyncio.sleep(7)
            await self.bot.delete_message(notif)

    async def renew(self, user):
        server = user.server
        chanp = self.sys[server.id]["PRISON_SALON"]
        role = self.sys[server.id]["PRISON_ROLE"]
        if "APPEL_SALON" not in self.sys[server.id]:
            self.sys[server.id]["APPEL_SALON"] = False
            self.sys[server.id]["APPEL_USE"] = []
        appel = True if self.sys[server.id]["APPEL_SALON"] else False
        apply = discord.utils.get(server.roles, name=role)
        if user.id in self.reg[server.id]:
            if role not in [r.name for r in user.roles]:
                if self.reg[server.id][user.id]["TS_SORTIE"] > time.time():
                    await self.bot.add_roles(user, apply)
                    if appel and user.id not in self.sys[server.id]["APPEL_USE"]:
                        self.sys[server.id]["APPEL_USE"].append(user.id)
                    estim = time.strftime("%H:%M", time.localtime(self.reg[server.id][user.id]["TS_SORTIE"]))
                    if chanp:
                        em = discord.Embed(description="**Retour automatique en prison** ─ "
                                                       "{} n'a pas terminé sa peine.".format(user.mention))
                        em.set_footer(text="Sortie estimée à {}".format(estim))
                        await self.bot.send_message(self.bot.get_channel(chanp), embed=em)
                    em = discord.Embed(description="**Retour en prison** ─ Vous n'avez pas terminé votre peine")
                    em.set_footer(text="Sortie estimée à {}".format(estim))
                    await self.bot.send_message(user, embed=em)
                    while time.time() < self.reg[server.id][user.id]["TS_SORTIE"]:
                        await asyncio.sleep(1)
                    if user in server.members:
                        if role in [r.name for r in user.roles]:
                            self.reg[server.id][user.id]["TS_ENTREE"] = self.reg[server.id][user.id]["TS_SORTIE"] = 0
                            await self.bot.remove_roles(user, apply)
                            if appel and user.id in self.sys[server.id]["APPEL_USE"]:
                                self.sys[server.id]["APPEL_USE"].remove(user.id)
                            em = discord.Embed(description="**Peine de prison** ─ Vous êtes désormais libre",
                                               color=apply.color)
                            await self.bot.send_message(user, embed=em)
                            if chanp:
                                rand = random.choice(
                                    ["est désormais libre", "regagne sa liberté", "est sorti de prison",
                                     "profite à nouveau de l'air frais"])
                                em = discord.Embed(description="{} {}".format(user.mention, rand), color=apply.color)
                                await self.bot.send_message(self.bot.get_channel(chanp), embed=em)
                            self.save()
                        else:
                            return
                    else:
                        if chanp:
                            em = discord.Embed(description="**Sortie de** <@{}> | Il n'est plus sur le serveur.")
                            self.add_event(user, "x<")
                            if appel and user.id in self.sys[server.id]["APPEL_USE"]:
                                self.sys[server.id]["APPEL_USE"].remove(user.id)
                            notif = await self.bot.send_message(self.bot.get_channel(chanp), embed=em)
                        else:
                            pass

    def levenshtein(self, s1, s2):
        if len(s1) < len(s2):
            m = s1
            s1 = s2
            s2 = m
        if len(s2) == 0:
            return len(s1)
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[
                                 j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    def normalize(self, texte: str):
        norm = [l for l in "neecaiuuo"]
        modif = [l for l in "ñéèçàîûùö"]
        fin_texte = texte
        for char in texte:
            if char in modif:
                ind = modif.index(char)
                fin_texte = fin_texte.replace(char, norm[ind])
        return fin_texte

    async def view(self, message):
        server = message.server
        author = message.author
        if not server:
            return
        if server.id not in self.sys:
            self.sys[server.id] = {}
        if "GLOBALSLOW" not in self.sys[server.id]:
            self.sys[server.id]["GLOBALSLOW"] = False
        if "SLOW" not in self.sys[server.id]:
            self.sys[server.id]["SLOW"] = {}
        if self.sys[server.id]["GLOBALSLOW"]:
            heure = time.strftime("%H:%M", time.localtime())
            if heure not in self.globalslow_cooldown:
                self.globalslow_cooldown = {heure: []}
            self.globalslow_cooldown[heure].append(author.id)
            if self.globalslow_cooldown[heure].count(author.id) > self.sys[server.id]["GLOBALSLOW"]:
                await self.bot.delete_message(message)

        if author.id in self.sys[server.id]["SLOW"]:
            heure = time.strftime("%H:%M", time.localtime())
            if heure not in self.slow_cooldown:
                self.slow_cooldown = {heure: []}
            self.slow_cooldown[heure].append(author.id)
            if self.slow_cooldown[heure].count(author.id) > self.sys[server.id]["SLOW"][author.id]:
                await self.bot.delete_message(message)

        if "FILTRE" not in self.sys[server.id]:
            self.sys[server.id]["FILTRE"] = {}
            self.save()
        splitted = message.content.split()
        for w in splitted:
            w = self.normalize(w)
            if w.lower() in self.sys[server.id]["FILTRE"]:
                roles = [r.name for r in author.roles]
                if author.id in self.sys[server.id]["FILTRE"][w.lower()]["CIBLE_USER"]:
                    await self.bot.delete_message(message)
                for r in roles:
                    if r in self.sys[server.id]["FILTRE"][w.lower()]["CIBLE_ROLE"]:
                        await self.bot.delete_message(message)
            liste = [m for m in self.sys[server.id]["FILTRE"]]
            for m in liste:
                if self.levenshtein(w.lower(), m.lower()) <= 1:
                    if self.sys[server.id]["FILTRE"][m]["SMART"]:
                        roles = [r.name for r in author.roles]
                        if author.id in self.sys[server.id]["FILTRE"][m.lower()]["CIBLE_USER"]:
                            await self.bot.delete_message(message)
                        for r in roles:
                            if r in self.sys[server.id]["FILTRE"][m.lower()]["CIBLE_ROLE"]:
                                await self.bot.delete_message(message)


def check_folders():
    folders = ("data", "data/justice/")
    for folder in folders:
        if not os.path.exists(folder):
            print("Création du fichier " + folder)
            os.makedirs(folder)


def check_files():
    if not os.path.isfile("data/justice/reg.json"):
        fileIO("data/justice/reg.json", "save", {})
    if not os.path.isfile("data/justice/sys.json"):
        fileIO("data/justice/sys.json", "save", {})


def setup(bot):
    check_folders()
    check_files()
    n = Justice(bot)
    bot.add_listener(n.view, "on_message")
    bot.add_listener(n.renew, "on_member_join")
    # bot.add_listener(n.reactprison, "on_reaction_add")
    bot.add_cog(n)