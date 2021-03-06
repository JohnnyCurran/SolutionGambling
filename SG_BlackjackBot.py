import time
from datetime import datetime
import praw
import ConfigParser
import random
# Config init
config = ConfigParser.ConfigParser()
config.read("settings.config")
config_header = "Blackjack"

subreddit_name = config.get("General", "subreddit")
username = config.get("General", "username")
version = config.get("General", "version")

# create our Reddit instance
c_id = config.get("General", "client_id")
c_secret = config.get("General", "client_secret")
user = config.get("General", "plain_username")
pw = config.get("General", "password")

thread_id = '6ov9sx'

CARDS = ( '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A' )
SUITS = ( 'C', 'D', 'H', 'S' )

random.seed(datetime.now())

reddit = praw.Reddit(
    client_id = c_id,
    client_secret = c_secret,
    username = user,
    password = pw,
    user_agent = 'Blackjack bot by /u/hifiduino version {}'.format(version)
)

def HandToString(hand):
    hand_string = ''
    for i, card in enumerate(hand):
        if i < len(hand) - 1:
            hand_string += hand[i] + ', '
        else:
            hand_string += hand[i]
    return hand_string

# Create reply for when player responds HIT
def DealerHandReply(player_hand, dealer_hand):
    reply_string = "Your hand is: " + HandToString(player_hand)
    reply_string += '\n\nThe dealer shows ' + HandToString(dealer_hand)
    reply_string += "\n\nReply HIT to receive another card\n\nReply STAND to end your turn"
    return reply_string

def DealCard(player_hand, dealer_hand):
    # Deal a card
    new_card = str(CARDS[random.randint(0, 12)] + ' ' + SUITS[random.randint(0, 3)])
    # make sure new card doesn't already exist in the hand
    if new_card not in player_hand and new_card not in dealer_hand:
        return new_card
    else:
        return DealCard(player_hand, dealer_hand)

# Convert card to numeral
def CardToNumeric(cardString):
    cardValue = cardString.strip().split(' ')[0]
    if (cardValue == 'A'):
        return 11
    try:
        int(cardValue)
        return int(cardValue)
    except ValueError:
        return 10

# Get the value of the current hand
def CalculateHandValue(hand):
    sum = 0
    for card in hand:
        sum += CardToNumeric(card)
    return sum

# Prevent dealer from replying to comments where user has already played hand
def HasReply(comment):
    comment.refresh()
    replies = comment.replies
    for reply in replies:
        if reply.author.name.lower() == user.lower():
            return True
    return False


# Is the person replying hit/stand the same person who began the game?
def IsGameStarter(comment, name_of_replier):
    ancestor = comment
    while not ancestor.is_root:
        ancestor = ancestor.parent()
    return ancestor.author.name.lower() == name_of_replier.lower()

def GetPlayerAction(comment):
    player_action = comment.body.split(' ')[0].strip().lower()
    if (player_action == 'wager' or player_action == 'hit' or player_action == 'stand'):
        print 'player action successful split'
        return player_action
    # if it's none of the above, try taking the substring
    stripped_comment = comment.body.strip()
    player_action = stripped_comment[:2]
    if player_action == 'hit':
        print 'player action hit'
        return player_action
    player_action = stripped_comment[:5]
    if player_action == 'wager' or player_action == 'stand':
        print 'player action stand'
        return player_action
    return None

# Main game flow control - what action should the bot take based on the comment?
def ProcessComment(comment):
    # Parse first word of comment to see action
    # player_action = comment.body.split(' ')[0].strip().lower()
    player_action = GetPlayerAction(comment)
    if (player_action == None):
        return False
    if comment.is_root and player_action == 'wager' and not HasReply(comment):
        # Begin game
        BeginGame(comment)
    # hit cannot be an action if not root comment, do not double reply to a hit
    if not comment.is_root and player_action == 'hit' and not HasReply(comment) and IsGameStarter(comment, comment.author.name):
        # Deal a card - calculate new hand value - reply with new hand or end the game as a loss
        PlayerHit(comment) # calculate new hand value, send reply or end game
    if not comment.is_root and player_action == 'stand' and not HasReply(comment) and IsGameStarter(comment, comment.author.name):
        PlayerStand(comment)

def BeginGame(comment):
    # Reply to comment with player & dealer deal
    flop = [DealCard((), ())]
    flop.append(DealCard(flop, ()))
    dealerHand = [DealCard(flop, ())]
    # did the dealer win on the flop?
    if not Blackjack(comment, flop, dealerHand):
        comment.reply(DealerHandReply(flop, dealerHand))

def Blackjack(comment, flop, dealer_hand):
    if CalculateHandValue(dealer_hand) < 10:
        return False
    blackjack_hand = dealer_hand[:]
    blackjack_hand.append(DealCard(flop, blackjack_hand))
    blackjack_hand_value = CalculateHandValue(blackjack_hand)
    flop_value = CalculateHandValue(flop)
    if blackjack_hand_value == 21:
        GameResultReply(comment, flop, blackjack_hand, flop_value, 21, '**Blackjack!**')
        print 'dealer blackjack!'
        return True
    elif blackjack_hand_value == 21 and flop_value == 21:
        GameResultReply(comment, flop, blackjack_hand, 21, 21, 'Game push')
        print 'game push!'
        return True

# determine if a hand is holding an ace
def NumAcesInHand(hand):
    numAces = 0
    for card in hand:
        if CardToNumeric(card) == 11:
            numAces = numAces + 1 
    return numAces

def PlayerHit(comment):
    # Dealer must hit until > 17, at which time hand is compared to player
    dealer_comment = comment.parent()
    dealer_reply = dealer_comment.body
    # Get player hand 
    player_hand = dealer_reply.split(':')[1].strip().split('\n')[0].split(',')
    for i, card in enumerate(player_hand):
        player_hand[i] = card.strip()
    # Get dealer hand
    dealer_hand = dealer_reply.split('shows')[1].split('\n')[0].split(',')
    dealer_hand_value = CalculateHandValue(dealer_hand)
    # Get player cards
    # deal player a new card
    player_hand.append(DealCard(player_hand, dealer_hand))
    handValue = CalculateHandValue(player_hand)
    ### Perform check to see if player is over 21 - if player has ace, subtract 10 from hand value
    num_player_aces = NumAcesInHand(player_hand)
    while num_player_aces > 0 and handValue > 21:
        handValue = handValue - 10
        num_player_aces = num_player_aces - 1
    #if HasAce(player_hand) and handValue > 21:
    #    handValue = handValue - 10
    if handValue <= 21:
        comment.reply(DealerHandReply(player_hand, dealer_hand))
    if handValue > 21:
        result_string = "**You busted!**"
        GameResultReply(comment, player_hand, dealer_hand, handValue, CalculateHandValue(dealer_hand), result_string) 

def PlayerStand(comment):
    # Dealer must hit until > 17, at which time hand is compared to player
    dealer_comment = comment.parent()
    dealer_reply = dealer_comment.body
    # Get player hand 
    player_hand = dealer_reply.split(':')[1].strip().split('\n')[0].split(',')
    for i, card in enumerate(player_hand):
        player_hand[i] = card.strip()
    # Get dealer hand
    dealer_hand = dealer_reply.split('shows')[1].split('\n')[0].split(',')
    dealer_hand_value = CalculateHandValue(dealer_hand)
    while dealer_hand_value < 17:
        dealer_hand.append(DealCard(player_hand, dealer_hand))
        num_dealer_aces = NumAcesInHand(dealer_hand)
        dealer_hand_value = CalculateHandValue(dealer_hand)
        # Make sure dealer doesn't bust if dealt an ace
        while num_dealer_aces > 0 and dealer_hand_value > 21:
            dealer_hand_value = dealer_hand_value - 10
            num_dealer_aces = num_dealer_aces - 1
    # Hand value is over 17, evaluate
    EvaluateHands(comment, player_hand, dealer_hand)

def EvaluateHands(comment, player_hand, dealer_hand):
    player_hand_value = CalculateHandValue(player_hand)
    dealer_hand_value = CalculateHandValue(dealer_hand)
    result_string = ''
    if player_hand_value > 21:
        result_string = "You busted! **Dealer wins!**"
    elif dealer_hand_value > 21:
        result_string = "Dealer busted! **You win!**"
    elif player_hand_value > dealer_hand_value:
        result_string="**You win!**"
    elif dealer_hand_value > player_hand_value:
        result_string = "**Dealer wins!**"
    elif dealer_hand_value == player_hand_value:
        result_string = "**Game push!**"
    GameResultReply(comment, player_hand, dealer_hand, player_hand_value, dealer_hand_value, result_string)

def GameResultReply(comment, player_hand, dealer_hand, player_hand_value, dealer_hand_value, result_string):
    replyString = "Your hand: " + HandToString(player_hand)
    replyString += "\n\nDealer hand: " + HandToString(dealer_hand)
    replyString += '\n\n You have {} and the Dealer has {}. {}'.format(player_hand_value, dealer_hand_value, result_string)
    comment.reply(replyString)

### MAIN LOOP ###
def bot_loop():
    for comment in reddit.subreddit(subreddit_name).stream.comments():
        if comment.submission.id == thread_id:
            ProcessComment(comment) 

if __name__ == '__main__':
    bot_loop()
