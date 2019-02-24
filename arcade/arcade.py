import asyncio
import os
import random

import discord
from discord.ext import commands

from .utils.dataIO import dataIO, fileIO


class Arcade:
    """Arcade | Ensemble de mini-jeux de combat"""

    def __init__(self, bot):
        self.bot = bot
        self.data = dataIO.load_json("data/arcade/data.json")
        try:
            self.pay = self.bot.get_cog("Pay").pay
        except:
            self.pay = None
        self.meta = {"on_channel": [], "reset": False}

    def save(self):
        fileIO("data/arcade/data.json", "save", self.data)
        return True

    @commands.command(aliases=["loot"], pass_context=True)
    async def lootbrawl(self, ctx, opposant: discord.Member = None):
        """Combattre dans l'arène de Loot Brawl"""
        author = ctx.message.author
        channel = ctx.message.channel
        server = ctx.message.server
        if self.pay == None:
            await self.bot.say("**Erreur** ─ Impossible de contacter l'extension **Pay**")
            return

        def check(reaction, user):
            return not user.bot

        if channel.id in self.meta["on_channel"]:
            await self.bot.say("**Impossible** ─ Il ne peut pas y avoir plus d'un combat par salon, attendez votre tour !")
            return

        if opposant:
            if self.pay.get_account(opposant):
                txt = "{} · **Loot Brawl** ─ **{}** vous a défié, acceptez-vous ?".format(opposant.mention, author.name)
                notif = await self.bot.say(txt)
                await self.bot.add_reaction(notif, "⚔")
                await self.bot.add_reaction(notif, "🏳")
                await asyncio.sleep(0.1)

                rep = await self.bot.wait_for_reaction(["⚔", "🏳"], message=notif, timeout=60, check=check,
                                                       user=opposant)
                if rep is None or rep.reaction.emoji == "🏳":
                    await self.bot.clear_reactions(notif)
                    await self.bot.edit_message(notif, "{} · **Loot Brawl** ─ Combat refusé".format(opposant.mention))
                    return
                elif rep.reaction.emoji == "⚔":
                    await self.bot.delete_message(notif)
            else:
                await self.bot.say("**Impossible** ─ Cette personne doit d'abord créer un compte bancaire **Pay**")
                return
        else:
            txt = "Qui sera l'adversaire de {} ?".format(author.mention)
            em = discord.Embed(title="Loot Brawl ─ En attente d'adversaire", description=txt, color=0xbc1c1c)
            em.set_footer(text="Cliquez sur ⚔ pour accepter le combat ··· Expire dans 120s")
            notif = await self.bot.say(embed=em)
            await self.bot.add_reaction(notif, "⚔")
            await asyncio.sleep(0.1)
            rep = await self.bot.wait_for_reaction(["⚔"], message=notif, timeout=120, check=check)
            if rep is None or rep.reaction.emoji == "⚔":
                await self.bot.delete_message(notif)
                if not rep.user.bot and self.pay.get_account(rep.user):
                    if rep.user != ctx.message.author:
                        opposant = rep.user
                    else:
                        await self.bot.say("**Impossible** ─ Vous ne pouvez pas vous battre avec vous-même !")
                        return
                else:
                    await self.bot.say("**Impossible** ─ Cette personne doit d'abord créer un compte bancaire **Pay**")
                    return

        emots = "⚔ 🛡 💊 💎 ⚖"
        items = [("Rascasse", 6, 0, 0, 0, "⚔"),
                 ("Lance-Belvita™", 4, 0, 1, 1, "⚔"),
                 ("Elixir de MSTs", 1, 0, 4, 1, "💊"),
                 ("Bilboquet", 2, 2, 0, 2, "⚖"),
                 ("Benalla", 2, 4, 0, 2, "🛡"),
                 ("Kro' périmée", 0, 1, 4, 1, "💊"),
                 ("Fléau Cactus", 4, 1, 0, 0, "⚔"),
                 ("Dague enchiassée", 3, 1, 0, 2, "⚔"),
                 ("Bombedanu", 5, 0, 0, 3, "⚔"),
                 ("Fronde à barres Feed™", 3, 0, 1, 0, "⚔"),
                 ("Ecu Sodebo™", 0, 4, 0, 2, "🛡"),
                 ("Rosebud purificateur", 0, 2, 2, 4, "💎"),
                 ("Casquette Daunat™", 0, 4, 1, 0, "🛡"),
                 ("Porte blindée d'Yllys'", 0, 6, 0, 0, "🛡"),
                 ("Doc Martens™ underground", 0, 3, 0, 2, "🛡"),
                 ("Vieux Papes™ millénaire", 1, 1, 4, 0, "💊"),
                 ("Pâtes au pesto'", 0, 2, 3, 1, "⚖"),
                 ("Verre de pesse", 0, 1, 5, 0, "💊"),
                 ("Platane centenaire", 2, 4, 0, 2, "🛡"),
                 ("Claquette oppressante", 3, 0, 0, 2, "⚔")]
        # 0.Nom 1.Atk 2.Def 3.PV 4.Priorité 5.Spé
        totalmoney = 50

        if channel.id not in self.meta["on_channel"]:
            self.meta["on_channel"].append(channel.id)
        else:
            await self.bot.say(
                "**Impossible** ─ Il ne peut pas y avoir plus d'un combat par salon, attendez votre tour !")
            return
        self.meta["on_channel"].append(channel.id)

        # Opposant -------------------------------------------------------------------------
        txt = random.choice(["Ci-dessous votre Starter gratuit. Voulez-vous acheter une nouvelle lootbox et tenter d'avoir mieux ? (**{}**g)",
                            "Voici votre Starter, il est offert. Vous pouvez acheter une nouvelle lootbox pour peut-être avoir mieux, vous voulez tester ? (**{}**g)",
                            "Ceci est votre lootbox de départ gratuite, mais vous pouvez acheter une autre lootbox et tenter d'avoir mieux, ça vous dit ? (**{}**g)"])
        n = offre = 0
        choisi = False
        notif = None
        while not choisi:
            n += 1
            lootbox = random.sample(items, 2)
            if n < 3:
                if n == 2:
                    txt = "Voilà une autre lootbox. Tu peux essayer d'en avoir encore une autre mais ça sera la dernière ! Tu veux tenter ? (**{}**g)"
                paygold = 25 * (n*n)
                em = discord.Embed(title="Loot Brawl ─ Choix de lootbox de {}".format(opposant.name),
                                   description=txt.format(paygold), color=opposant.color)
                em.set_footer(text="💰 ─ Payer {}g | ✅ ─ Partir se battre".format(paygold))
                for item in lootbox:
                    stats = "**Attaque** ─ +{}\n" \
                            "**Défense** ─ +{}\n" \
                            "**Bonus PV** ─ +{}\n" \
                            "**Priorité** ─ #{}".format(item[1], item[2], item[3], item[4])
                    em.add_field(name="{} ({})".format(item[0], item[5]), value=stats)
                if not notif:
                    notif = await self.bot.say(embed=em)
                else:
                    await self.bot.edit_message(notif, embed=em)
                    await self.bot.clear_reactions(notif)
                    await asyncio.sleep(0.1)
                await self.bot.add_reaction(notif, "💰")
                await self.bot.add_reaction(notif, "✅")
                await asyncio.sleep(0.1)

                rep = await self.bot.wait_for_reaction(["💰", "✅"], message=notif, timeout=40, check=check,
                                                       user=opposant)
                if rep is None or rep.reaction.emoji == "✅":
                    await self.bot.clear_reactions(notif)
                    em.set_footer(text="Voilà donc votre loot ! C'est à votre adversaire de choisir le siens désormais...")
                    em.description = "Choix confirmé !"
                    await self.bot.edit_message(notif, embed=em)
                    choisi = True
                elif rep.reaction.emoji == "💰":
                    if self.pay.enough_credits(opposant, paygold):
                        offre += paygold
                        totalmoney += paygold
                        self.pay.remove_credits(opposant, paygold, "LB Achat de lootbox")
                        continue
                    else:
                        await self.bot.clear_reactions(notif)
                        em.set_footer(text="Voilà donc votre loot ! C'est à votre adversaire de choisir le siens désormais...")
                        em.description = "Pas assez d'argent, vous allez donc devoir combattre avec ces items."
                        await self.bot.edit_message(notif, embed=em)
                        choisi = True
                else:
                    return
            else:
                await self.bot.clear_reactions(notif)
                txt = "Voilà donc votre lootbox de la dernière chance. Bonne chance !"
                em = discord.Embed(title="Loot Brawl ─ Choix de lootbox de {}".format(opposant.name), description=txt,
                                   color=opposant.color)
                em.set_footer(text="C'est désormais à votre adversaire de choisir son loot...")
                for item in lootbox:
                    stats = "**Attaque** ─ +{}\n" \
                            "**Défense** ─ +{}\n" \
                            "**Bonus PV** ─ +{}\n" \
                            "**Priorité** ─ #{}".format(item[1], item[2], item[3], item[4])
                    em.add_field(name="{} ({})".format(item[0], item[5]), value=stats)
                await self.bot.edit_message(notif, embed=em)
                choisi = True
        stats_opposant = {"items": lootbox,
                          "prior": max([i[4] for i in lootbox]),
                          "stats": {"atk": 12,
                                  "def": 2,
                                  "pv": 100},
                          "offre": offre}

        # Auteur --------------------------------------------------------------------
        txt = random.choice(["Ci-dessous votre Starter gratuit. Voulez-vous acheter une nouvelle lootbox et tenter d'avoir mieux ? (**{}**g)",
                            "Voici votre Starter, il est offert. Vous pouvez acheter une nouvelle lootbox pour peut-être avoir mieux, vous voulez tester ? (**{}**g)",
                            "Ceci est votre lootbox de départ gratuite, mais vous pouvez acheter une autre lootbox et tenter d'avoir mieux, ça vous dit ? (**{}**g)"])
        n = offre = 0
        choisi = False
        notif = None
        while not choisi:
            n += 1
            lootbox = random.sample(items, 2)
            if n < 3:
                if n == 2:
                    txt = "Voilà une autre lootbox. Tu peux essayer d'en avoir encore une autre mais ça sera la dernière ! Tu veux tenter ? (**{}**g)"
                paygold = 25 * (n * n)
                em = discord.Embed(title="Loot Brawl ─ Choix de lootbox de {}".format(author.name), description=txt.format(paygold),
                                   color=author.color)
                em.set_footer(text="💰 ─ Payer {}g | ✅ ─ Partir se battre".format(paygold))
                for item in lootbox:
                    stats = "**Attaque** ─ +{}\n" \
                            "**Défense** ─ +{}\n" \
                            "**Bonus PV** ─ +{}\n" \
                            "**Priorité** ─ #{}".format(item[1], item[2], item[3], item[4])
                    em.add_field(name="{} ({})".format(item[0], item[5]), value=stats)
                if not notif:
                    notif = await self.bot.say(embed=em)
                else:
                    await self.bot.edit_message(notif, embed=em)
                    await self.bot.clear_reactions(notif)
                    await asyncio.sleep(0.1)
                await self.bot.add_reaction(notif, "💰")
                await self.bot.add_reaction(notif, "✅")
                await asyncio.sleep(0.1)

                rep = await self.bot.wait_for_reaction(["💰", "✅"], message=notif, timeout=40, check=check,
                                                       user=author)
                if rep is None or rep.reaction.emoji == "✅":
                    await self.bot.clear_reactions(notif)
                    em.set_footer(
                        text="Voilà donc votre loot ! Le combat va commencer !")
                    em.description = "Choix confirmé !"
                    await self.bot.edit_message(notif, embed=em)
                    choisi = True
                elif rep.reaction.emoji == "💰":
                    if self.pay.enough_credits(author, paygold):
                        offre += paygold
                        totalmoney += paygold
                        self.pay.remove_credits(author, paygold, "LB Achat de lootbox")
                        continue
                    else:
                        await self.bot.clear_reactions(notif)
                        em.set_footer(
                            text="Voilà donc votre loot ! Le combat va commencer !")
                        em.description = "Pas assez d'argent, vous allez donc devoir combattre avec ces items."
                        await self.bot.edit_message(notif, embed=em)
                        choisi = True
                else:
                    return
            else:
                await self.bot.clear_reactions(notif)
                txt = "Voilà donc votre lootbox de la dernière chance. Bonne chance !"
                em = discord.Embed(title="Loot Brawl ─ Choix de lootbox de {}".format(author.name), description=txt,
                                   color=author.color)
                em.set_footer(text="Préparez-vous, le combat va bientôt commencer !")
                for item in lootbox:
                    stats = "**Attaque** ─ +{}\n" \
                            "**Défense** ─ +{}\n" \
                            "**Bonus PV** ─ +{}\n" \
                            "**Priorité** ─ #{}".format(item[1], item[2], item[3], item[4])
                    em.add_field(name="{} ({})".format(item[0], item[5]), value=stats)
                await self.bot.edit_message(notif, embed=em)
                choisi = True
        stats_author = {"items": lootbox,
                        "prior": max([i[4] for i in lootbox]),
                        "stats": {"atk": 12,
                                  "def": 2,
                                  "pv": 100},
                        "offre": offre}

        if stats_author["prior"] == stats_opposant["prior"]:
            i = random.randint(0, 1)
            if i == 1:
                stats_author["prior"] += 1
                await self.bot.say("**Bonus** ─ {} a reçu un bonus de *Priorité* (Egalité)".format(author.name))
            else:
                stats_opposant["prior"] += 1
                await self.bot.say("**Bonus** ─ {} a reçu un bonus de *Priorité* (Egalité)".format(opposant.name))

        if stats_author["prior"] > stats_opposant["prior"]:
            first = stats_author
            first_user = author
            second = stats_opposant
            second_user = opposant
            em = discord.Embed(title="Loot Brawl ─ Récapitulatif", description="{} VS {}".format(author.mention, opposant.mention))
            txt = ""
            for item in stats_author["items"]:
                stats_author["stats"]["atk"] += item[1]
                stats_author["stats"]["def"] += item[2]
                stats_author["stats"]["pv"] += 5 * item[3]
                txt += "**{}** ─ {}/{}/{}\n".format(item[0], item[1], item[2], item[3])
            txt += "**Total** ─ {}/{}/{}".format(stats_author["stats"]["atk"], stats_author["stats"]["def"],
                                                 stats_author["stats"]["pv"])
            em.add_field(name="1 · "+ author.name, value=txt)

            txt = ""
            for item in stats_opposant["items"]:
                stats_opposant["stats"]["atk"] += item[1]
                stats_opposant["stats"]["def"] += item[2]
                stats_opposant["stats"]["pv"] += 5 * item[3]
                txt += "**{}** ─ {}/{}/{}\n".format(item[0], item[1], item[2], item[3])
            txt += "**Total** ─ {}/{}/{}".format(stats_opposant["stats"]["atk"], stats_opposant["stats"]["def"],
                                                 stats_opposant["stats"]["pv"])
            em.add_field(name="2 · " + opposant.name, value=txt)
            em.set_footer(text="Que le combat COMMENCE !")
            await self.bot.say(embed=em)

        else:
            first = stats_opposant
            first_user = opposant
            second = stats_author
            second_user = author
            em = discord.Embed(title="Loot Brawl ─ Récapitulatif", description="{} VS {}".format(author.mention, opposant.mention))
            txt = ""
            for item in stats_opposant["items"]:
                stats_opposant["stats"]["atk"] += item[1]
                stats_opposant["stats"]["def"] += item[2]
                stats_opposant["stats"]["pv"] += 5 * item[3]
                txt += "**{}** ─ {}/{}/{}\n".format(item[0], item[1], item[2], item[3])
            txt += "**Total** ─ {}/{}/{}".format(stats_opposant["stats"]["atk"], stats_opposant["stats"]["def"],
                                                 stats_opposant["stats"]["pv"])
            em.add_field(name="1 · " + opposant.name, value=txt)

            txt = ""
            for item in stats_author["items"]:
                stats_author["stats"]["atk"] += item[1]
                stats_author["stats"]["def"] += item[2]
                stats_author["stats"]["pv"] += 5 * item[3]
                txt += "**{}** ─ {}/{}/{}\n".format(item[0], item[1], item[2], item[3])
            txt += "**Total** ─ {}/{}/{}".format(stats_author["stats"]["atk"], stats_author["stats"]["def"],
                                                 stats_author["stats"]["pv"])
            em.add_field(name="2 · "+ author.name, value=txt)
            em.set_footer(text="Que le combat COMMENCE !")
            await self.bot.say(embed=em)

        await asyncio.sleep(6)
        atkstr = ["**{0}** lance une attaque sur **{1}**",
                  "**{0}** se lance sur **{1}**",
                  "**{0}** attaque **{1}**",
                  "**{0}** charge **{1}**",
                  "**{1}** se fait aggresser par **{0}**",
                  "**{0}** cogne méchamment **{1}**",
                  "**{1}** se fait molester par **{0}**"]
        atkstr_crit = ["**{0}** lance une ATTAQUE CRITIQUE sur **{1}** !",
                       "**{1}** se prend une ATTAQUE CRITIQUE de la part de **{0}** !"]
        defstr_parf = ["Mais **{1}** réalise une DEFENSE PARFAITE contre l'attaque de **{0}** !",
                       "Mais **{1}** parvient à se dégager de **{0}** et fait une DEFENSE PARFAITE !"]
        cycle = 1
        action = 1
        dn = None
        while stats_author["stats"]["pv"] > 0 and stats_opposant["stats"]["pv"] > 0:
            if self.meta["reset"]:
                self.meta["on_channel"].remove(channel.id)
                if stats_author["offre"]:
                    self.pay.add_credits(author, stats_author["offre"], "Remboursement reset BR")
                if stats_opposant["offre"]:
                    self.pay.add_credits(opposant, stats_opposant["offre"], "Remboursement reset BR")
                await self.bot.say("**Partie stoppée** ─ Vous avez été remboursés en conséquence\n"
                                   "Pardonnez-moi pour la gêne occasionnée...")
                await asyncio.sleep(1)
                self.meta["reset"] = False
                return

            if cycle == 1:
                await self.bot.say("───── **QUE LE COMBAT COMMENCE** ─────")
                await asyncio.sleep(3)

            if first["stats"]["pv"] > 0:
                # Attaque de First sur Second
                f_atkcrit = True if random.randint(0, 8) == 0 else False
                s_defcrit = True if random.randint(0, 3) == 0 else False
                deg_fs = 0
                if f_atkcrit:
                    await self.bot.say("{} · ".format(action) + random.choice(atkstr_crit).format(first_user.name, second_user.name))
                    deg_fs += int(first["stats"]["atk"] * 1.5)
                    await asyncio.sleep(1)
                    if s_defcrit:
                        await self.bot.say("{} · ".format(action) + random.choice(defstr_parf).format(first_user.name, second_user.name))
                        deg_fs = 1
                else:
                    await self.bot.say("{} · ".format(action) + random.choice(atkstr).format(first_user.name, second_user.name))
                    deg_fs += first["stats"]["atk"]
                await asyncio.sleep(0.75)
                await self.bot.say("{} · Résultat {} ─ **-{}** PV ({})".format(action, second_user.name, deg_fs, second["stats"]["pv"]))
                second["stats"]["pv"] -= deg_fs
                await asyncio.sleep(2)
            else:
                dn = await self.bot.say("**{}** est KO !".format(first_user.name))

            if second["stats"]["pv"] > 0:
                # Attaque de Second sur First
                action += 1
                s_atkcrit = True if random.randint(0, 8) == 0 else False
                f_defcrit = True if random.randint(0, 3) == 0 else False
                deg_sf = 0
                if s_atkcrit:
                    await self.bot.say(
                        "{} · ".format(action) + random.choice(atkstr_crit).format(second_user.name, first_user.name))
                    deg_sf += int(second["stats"]["atk"] * 1.5)
                    await asyncio.sleep(1)
                    if f_defcrit:
                        await self.bot.say(
                            "{} · ".format(action) + random.choice(defstr_parf).format(second_user.name, first_user.name))
                        deg_sf = 1
                else:
                    await self.bot.say(
                        "{} · ".format(action) + random.choice(atkstr).format(second_user.name, first_user.name))
                    deg_sf += second["stats"]["atk"]
                await asyncio.sleep(0.75)
                await self.bot.say("{} · Résultat {} ─ **-{}** PV ({})".format(action, first_user.name, deg_sf, first["stats"]["pv"]))
                first["stats"]["pv"] -= deg_sf
                r = random.randint(1, 4)
                await asyncio.sleep(r)
            else:
                dn = await self.bot.say("**{}** est KO !".format(second_user.name))
            action += 1

        gagnant = first_user if first["stats"]["pv"] > 0 else second_user
        perdant = first_user if first["stats"]["pv"] == 0 else second_user
        if dn is None:
            await self.bot.say("**{}** est KO !".format(perdant.name))
            await asyncio.sleep(2.5)
        txt = "{} a gagné, il remporte **{}**g !".format(gagnant.mention, totalmoney)
        em = discord.Embed(title="Loot Brawl ─ Gagnant", description=txt, color=gagnant.color)
        await self.bot.say(embed=em)
        self.meta["on_channel"].remove(channel.id)
        self.pay.add_credits(gagnant, totalmoney, "Gagnant à Loot Brawl")
        return

    @commands.command(pass_context=True)
    async def resetlb(self, ctx):
        """Reset la partie Loot Brawl sur le salon"""
        self.meta["reset"] = True
        await self.bot.say("Reset en cours...")


def check_folders():
    if not os.path.exists("data/arcade"):
        print("Creation du dossier arcade...")
        os.makedirs("data/arcade")


def check_files():
    if not os.path.isfile("data/arcade/data.json"):
        print("Création de arcade/data")
        dataIO.save_json("data/arcade/data.json", {})

def setup(bot):
    check_folders()
    check_files()
    n = Arcade(bot)
    bot.add_cog(n)