# mcts_ai.py

import math
import random
from collections import defaultdict

# MCTS가 탐색하는 트리의 각 지점(노드)을 나타내는 클래스
class MCTS_Node:
    def __init__(self, game_state, parent=None, move=None):
        self.game_state = game_state
        self.parent = parent
        self.move = move  # 이 노드로 오게 된 '행동' (예: {'rank': 5, 'count': 3})
        
        self.children = []
        self.wins = 0
        self.visits = 0
        
        # 이 노드에서 아직 탐색해보지 않은 수들
        self.unexplored_moves = self.game_state.get_possible_moves()

    def select_child(self):
        """ UCB1 공식을 사용해 가장 유망한 자식 노드를 선택합니다. (Selection 단계) """
        # UCB1: (자신의 승률) + c * sqrt(log(부모의 방문 횟수) / (자신의 방문 횟수))
        # 승률이 높은 '익숙한 길'과, 아직 덜 가본 '새로운 길' 사이의 균형을 맞추는 역할
        log_total_visits = math.log(self.visits)
        
        def ucb_score(child):
            if child.visits == 0:
                return float('inf') # 아직 방문 안 한 노드를 최우선으로 탐색
            return (child.wins / child.visits) + 1.41 * math.sqrt(log_total_visits / child.visits)

        return sorted(self.children, key=ucb_score, reverse=True)[0]

    def expand(self):
        """ 아직 시도 안 한 수 중 하나를 골라 자식 노드를 만들고 트리를 확장합니다. (Expansion 단계) """
        move = self.unexplored_moves.pop()
        next_state = self.game_state.make_move(move)
        child_node = MCTS_Node(next_state, parent=self, move=move)
        self.children.append(child_node)
        return child_node

    def update(self, result):
        """ 시뮬레이션 결과를 자신과 모든 부모 노드들에게 거슬러 올라가며 전파합니다. (Backpropagation 단계) """
        self.visits += 1
        self.wins += result
        if self.parent:
            self.parent.update(result)

# MCTS 알고리즘의 전체 흐름을 제어하는 메인 클래스
class MCTS_AI:
    def __init__(self, iterations=1000):
        self.iterations = iterations # AI의 '생각하는 깊이'. 숫자가 클수록 똑똑하지만 느려짐.

    def find_best_move(self, initial_state):
        """ 주어진 상태에서 최선의 수를 찾습니다. """
        root_node = MCTS_Node(game_state=initial_state)
        
        # 주어진 횟수만큼 시뮬레이션 반복
        for _ in range(self.iterations):
            node = root_node
            
            # 1. Selection: 가장 유망한 경로를 따라 내려감
            while not node.unexplored_moves and node.children:
                node = node.select_child()
            
            # 2. Expansion: 새로운 수를 시도하며 트리 확장
            if node.unexplored_moves:
                node = node.expand()
            
            # 3. Simulation: 확장된 노드부터 게임 끝까지 무작위로 플레이
            winner_index = self._simulate(node.game_state)
            
            # 4. Backpropagation: 시뮬레이션 결과를 트리에 업데이트
            # 현재 MCTS AI의 승리 여부를 판단
            result = 1 if winner_index == initial_state.turn_index else 0
            node.update(result)

        # 모든 시뮬레이션 후, 가장 많이 방문한(가장 안정적이고 승률이 높다고 판단된) 수를 선택
        best_child = sorted(root_node.children, key=lambda c: c.visits, reverse=True)[0]
        return best_child.move

    def _simulate(self, game_state):
        """ 현재 상태에서 게임이 끝날 때까지 무작위로 플레이하고 승자를 반환합니다. (Simulation 단계) """
        current_state = game_state
        while not current_state.game_over:
            possible_moves = current_state.get_possible_moves()
            # 낼 수 있는 패가 없으면 무조건 패스
            if not possible_moves:
                move = "pass"
            else:
                move = random.choice(possible_moves)
            
            current_state = current_state.make_move(move)
        
        return current_state.winner_index