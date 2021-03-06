#!/usr/bin/python
# -*- coding: UTF-8 -*-

import simulator
import ftl_bot
import random
import tensorflow as tf
from DQNModel import PlayModel, KickersModel

def create_player(id,playmodel,kickersmodel,data,mode="Train",addHuman=[False,False,False]):
    player = ftl_bot.FTLBot(playmodel, kickersmodel, data, "Judge")
    if mode == "Test":
        #if id == 0:
        player = ftl_bot.FTLBot(playmodel, kickersmodel, data, "Judge", True, addHuman[id])
    
    return player

# Judge class for Fight The Landlord game
class FTLJudgement:

    # lastCardTable: the card table status of the previous game, influences shuffling
    def __init__(self, lastCardTable = [], isDebug = False):

        self.nowTurn = -1 # Not Played
        self.cardTable = [] # what cards are played now
        #self.isPlayed = [0] * 54 # is card id == k played

        self.playerHistory = [[], [], []] # The play history of three players
        self.last2Plays = [[], []] # Record the most recent previous 2 plays

        self.isDebug = isDebug
        self.cards = lastCardTable
        if not lastCardTable: # no previous information
            self.cards = list(range(0, 54))
            random.shuffle(self.cards)

        self.publicCards = self.cards[0 : 3] # included in Landlord cards
        self.cardsPlayer = [self.cards[0 : 20], self.cards[20 : 37], self.cards[37 : 54]] # Landlord, Farmer 1, Farmer 2
        self.publicCards.sort()
        self.cardsPlayer[0].sort()
        self.cardsPlayer[1].sort()
        self.cardsPlayer[2].sort()
        self.nowCardsPlayer = [self.cardsPlayer[i][:] for i in range(3)] # deep copy

        self.log("Public cards are "+simulator.CardInterpreter.getCardName(self.publicCards))
        for player in range(3):
            self.log("Serve Player %d : "%(player)+simulator.CardInterpreter.getCardName(self.nowCardsPlayer[player]))

    # debug_print
    def log(self, text):
        if self.isDebug:
            print("Turn %d: %s"%(self.nowTurn, text))

    # simulate the game process
    def work(self, playmodel, kickersmodel, nowep, mode="Train",addHuman=[False,False,False]):
        isGameFinished = False
        score = [0,0,0]
        winner = -1
        while not isGameFinished: # Looping
            self.nowTurn += 1;
            for playerID in range(3): # 3 players
                data = {"ID": playerID, "nowTurn": self.nowTurn, "publicCard": self.publicCards}
                data["history"] = self.playerHistory
                data["deal"] = self.cardsPlayer[playerID]
                player = create_player(playerID, playmodel[playerID], kickersmodel, data, mode, addHuman)
                cardsPlayed = player.makeDecision()
                self.log("Player %d [%d] card %s"%(playerID, \
                    len(self.nowCardsPlayer[playerID]), \
                    simulator.CardInterpreter.getCardName(cardsPlayed)))

                # checks applied
                for c in cardsPlayed:
                    if not c in self.nowCardsPlayer[playerID]: # player played a card it not owned
                        self.log("Card %s is not owned"%simulator.CardInterpreter.getCardName(c))
                        isGameFinished = True
                        break
                if isGameFinished: break

                hand = simulator.Hand(cardsPlayed)
                score[playerID] += hand.getHandScore()
                if hand.type == "None": # Not avaliable pattern
                    self.log("The pattern is not recognized")
                    isGameFinished = True
                    break

                if hand.chain >= 2 and hand.primal == 12: # 2 in a chain
                    self.log("Card 2 in a chain")
                    isGameFinished = True
                    break

                lastCards = self.last2Plays[1] or self.last2Plays[0]
                lastHand = simulator.Hand(lastCards)
                if not hand.isAbleToFollow(lastHand): # can't cover the last hand
                    self.log("Cards can't follow the last hand %s"%simulator.CardInterpreter.getCardName(lastCards))
                    isGameFinished = True
                    break

                # LEGAL
                self.last2Plays[0] = self.last2Plays[1]
                self.last2Plays[1] = cardsPlayed
                for c in cardsPlayed:
                    self.nowCardsPlayer[playerID].remove(c)
                self.playerHistory[playerID].append(cardsPlayed)
                self.cardTable.extend(cardsPlayed)

                if not len(self.nowCardsPlayer[playerID]): # Finished
                    result = self.report(playerID, score)
                    isGameFinished = True
                    winner = playerID
                    break
            if self.isDebug:
                print(score)
                input("Press <ENTER> to continue...")

        self.log("Game finished")
        kickersmodel.finishEpisode(playmodel,score,mode=="Train")
        turnscores = [[],[],[]]
        # @TODO Add Model Training        
        for playerID in range(3): # discard cards to table
            self.cardTable.extend(self.nowCardsPlayer[playerID])
            turnscores[playerID] = playmodel[playerID].finishEpisode(score[playerID],mode=="Train")
            #playmodel[playerID].finishEpisode(turnscores[playerID], nowep>1000)

        return winner,score,self.cardTable
    
    def getFinalScore(self,winner,score):
        farmerScore = (score[1] + score[2]) / 2.0
        #dis = score[0] - farmerScore / 2.0
        score[1] = score[2] = 50 - 0.5 * score[0] + farmerScore
        score[0] = 50 + score[0] - 0.5 * farmerScore
        if winner == 0:
            score[0] += 100
        else:
            score[1] += 100
            score[2] = score[1]
        return score      

    # Report the result
    def report(self, winner, score):
        self.log("The winner is bot %d"%winner)
        # Score calculation
        score = self.getFinalScore(winner,score)
        print("Final Score:"+str(score))
