# dalmuti_game.py (Simulation-Only Version)

import random
from collections import Counter
import copy

# ==============================================================================
# Player 클래스
# ==============================================================================
class Player:
    def __init__(self, name, is_ai=False, style='balanced'):
        self.name = name
        self.is_ai = is_ai
        self.style = style
        self.hand = []

    def sort_hand(self):
        self.hand.sort()

# ==============================================================================
# GameState 클래스 (핵심 로직)
# ==============================================================================
class GameState:
    def __init__(self, player_styles, is_clone=False):
        if is_clone:
            return

        self.players = []
        is_human_in_game = "You" in player_styles
        for i, style in enumerate(player_styles):
            is_ai = not is_human_in_game or style != "You"
            name = "You" if not is_ai and is_human_in_game else f"AI {i if is_human_in_game else i + 1}"
            self.players.append(Player(name, is_ai=is_ai, style=style))
        
        self.num_players = len(self.players)
        self.turn_index = 0
        self.round_lead_index = 0
        self.table_cards = {'cards': [], 'effective_rank': 0}
        self.passed_in_round = set()
        self.consecutive_passes = 0
        self.game_over = False
        self.winner_index = -1
        self.game_log = [] # 시뮬레이션 중에는 사용되지 않지만, 구조 유지를 위해 남겨둠
        self._setup_deck_and_deal()

    def _setup_deck_and_deal(self):
        deck = [c for i in range(1, 13) for c in [i] * i] + [13, 13]
        random.shuffle(deck)
        for i, card in enumerate(deck):
            self.players[i % self.num_players].hand.append(card)
        for p in self.players:
            p.sort_hand()
        self.turn_index = self.round_lead_index = random.randint(0, self.num_players - 1)

    def clone(self):
        cloned_state = GameState([], is_clone=True)
        cloned_state.num_players = self.num_players
        cloned_state.players = copy.deepcopy(self.players)
        cloned_state.turn_index = self.turn_index
        cloned_state.round_lead_index = self.round_lead_index
        cloned_state.table_cards = copy.deepcopy(self.table_cards)
        cloned_state.passed_in_round = self.passed_in_round.copy()
        cloned_state.consecutive_passes = self.consecutive_passes
        cloned_state.game_over = self.game_over
        cloned_state.winner_index = self.winner_index
        cloned_state.game_log = []
        return cloned_state

    def get_current_player(self):
        return self.players[self.turn_index]

    def get_possible_moves(self):
        if self.turn_index in self.passed_in_round:
            return ["pass"]
        
        moves = []
        player = self.players[self.turn_index]
        hand_counts = Counter(player.hand)
        num_jokers = hand_counts.get(13, 0)
        
        # 1. 조커 없이 내는 경우
        for r, c in hand_counts.items():
            if r == 13: continue
            if self.is_valid_move(self.turn_index, r, c):
                moves.append({'rank': r, 'count': c})

        # 2. 다른 카드와 조커를 '섞어서' 내는 경우
        if num_jokers > 0:
            for r, c in hand_counts.items():
                if r == 13: continue
                for j in range(1, num_jokers + 1):
                    if self.is_valid_move(self.turn_index, r, c + j):
                        moves.append({'rank': r, 'count': c + j})

        # 3. 조커'만' 단독으로 내는 경우 (rank를 13으로 명시)
        if num_jokers > 0:
            for c in range(1, num_jokers + 1):
                if self.is_valid_move(self.turn_index, 13, c):
                    moves.append({'rank': 13, 'count': c})
        
        # 라운드 시작 시에는 패스 불가
        if not self.table_cards['cards'] and not moves:
             pass
        else:
            moves.append("pass")
        return moves

    def make_move(self, move):
        new_state = self.clone()
        if move == "pass":
            new_state.player_pass(new_state.turn_index)
        else:
            new_state.play_cards(new_state.turn_index, move['rank'], move['count'])
        return new_state

    def is_valid_move(self, player_index, rank, count):
        player = self.players[player_index]
        if player_index in self.passed_in_round: return False
        
        num_jokers = player.hand.count(13)
        if rank == 13:
            if num_jokers < count: return False
        else:
            num_native = player.hand.count(rank)
            if num_native + num_jokers < count: return False
        
        if not self.table_cards['cards']: return True
        if count == len(self.table_cards['cards']) and rank < self.table_cards['effective_rank']: return True
        return False

    def play_cards(self, player_index, rank, count):
        player = self.players[player_index]
        if rank == 13:
            to_remove = {'native': 0, 'jokers': count}
        else:
            native_available = player.hand.count(rank)
            jokers_to_use = count - native_available if native_available < count else 0
            native_to_use = count - jokers_to_use
            to_remove = {'native': native_to_use, 'jokers': jokers_to_use}
        
        for _ in range(to_remove['native']): player.hand.remove(rank)
        for _ in range(to_remove['jokers']): player.hand.remove(13)

        played_list = [rank] * to_remove['native'] + [13] * to_remove['jokers']
        played_list.sort()
        self.table_cards = {'cards': played_list, 'effective_rank': rank}
        self.consecutive_passes = 0
        self.round_lead_index = player_index

        if not player.hand:
            self.game_over = True
            self.winner_index = player_index
            return
        self.advance_turn()

    def player_pass(self, player_index):
        self.passed_in_round.add(player_index)
        self.consecutive_passes += 1
        
        active_players_with_cards = [p for p in self.players if p.hand]
        unpassed_players = [p for p in active_players_with_cards if self.players.index(p) not in self.passed_in_round]

        if len(unpassed_players) <= 1 and len(active_players_with_cards) > 1:
            self.table_cards = {'cards': [], 'effective_rank': 0}
            self.consecutive_passes = 0
            self.passed_in_round.clear()
            self.turn_index = self.round_lead_index
            if not self.players[self.turn_index].hand: self.advance_turn()
        else:
            self.advance_turn()

    def advance_turn(self):
        if self.game_over: return
        self.turn_index = (self.turn_index + 1) % self.num_players
        while not self.players[self.turn_index].hand:
            self.turn_index = (self.turn_index + 1) % self.num_players
