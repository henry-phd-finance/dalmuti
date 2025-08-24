# mcts_pro.py
import math
import random
import copy

class MCTS_Pro_Node:
    def __init__(self, game_state, parent=None, move=None):
        self.game_state = game_state
        self.parent = parent
        self.move = move
        self.children = []
        self.wins = 0
        self.visits = 0
        self.unexplored_moves = self.game_state.get_possible_moves()

    def select_child(self):
        log_total_visits = math.log(self.visits)
        def ucb_score(child):
            if child.visits == 0:
                return float('inf')
            return (child.wins / child.visits) + 1.41 * math.sqrt(log_total_visits / child.visits)
        return sorted(self.children, key=ucb_score, reverse=True)[0]

    def expand(self):
        move = self.unexplored_moves.pop()
        next_state = self.game_state.make_move(move)
        child_node = MCTS_Pro_Node(next_state, self, move)
        self.children.append(child_node)
        return child_node

    def update(self, result):
        self.visits += 1
        self.wins += result
        if self.parent:
            self.parent.update(result)

class MCTS_Pro_AI:
    def __init__(self, iterations=1000):
        self.iterations = iterations

    def _create_determinized_state(self, current_state):
        determinized_state = current_state.clone()
        root_player_index = current_state.turn_index
        my_hand = current_state.players[root_player_index].hand
        table_cards = current_state.table_cards['cards']

        full_deck = [c for i in range(1, 13) for c in [i] * i] + [13, 13]
        
        known_cards = my_hand + table_cards
        
        # Count occurrences of each card
        known_counts = {}
        for card in known_cards:
            known_counts[card] = known_counts.get(card, 0) + 1
            
        unknown_card_pool = []
        full_deck_counts = {}
        for card in full_deck:
            full_deck_counts[card] = full_deck_counts.get(card, 0) + 1

        for card, count in full_deck_counts.items():
            unknown_count = count - known_counts.get(card, 0)
            if unknown_count > 0:
                unknown_card_pool.extend([card] * unknown_count)

        random.shuffle(unknown_card_pool)

        card_pool_index = 0
        for i, player in enumerate(determinized_state.players):
            if i != root_player_index:
                hand_size = len(player.hand)
                player.hand = unknown_card_pool[card_pool_index : card_pool_index + hand_size]
                player.sort_hand()
                card_pool_index += hand_size
        
        return determinized_state

    def find_best_move(self, initial_state):
        root_node = MCTS_Pro_Node(initial_state)
        root_player_index = initial_state.turn_index

        for _ in range(self.iterations):
            node = root_node
            
            while not node.unexplored_moves and node.children:
                node = node.select_child()
            
            if node.unexplored_moves:
                node = node.expand()

            determinized_state = self._create_determinized_state(node.game_state)

            sim_state = determinized_state
            safety_break = 0
            while not sim_state.game_over and safety_break < 100:
                moves = sim_state.get_possible_moves()
                random_move = random.choice(moves)
                sim_state = sim_state.make_move(random_move)
                safety_break += 1

            result = 1 if sim_state.winner_index == root_player_index else 0
            node.update(result)

        if not root_node.children:
            return "pass"
            
        best_child = sorted(root_node.children, key=lambda c: c.visits, reverse=True)[0]
        return best_child.move
