// 결정화(Determinization) 기법이 적용된 MCTS AI 로직

class MCTS_Pro_Node {
    constructor(gameState, parent = null, move = null) {
        this.gameState = gameState;
        this.parent = parent;
        this.move = move;
        this.children = [];
        this.wins = 0;
        this.visits = 0;
        this.unexploredMoves = this.gameState.get_possible_moves();
    }
    select_child() {
        const logTotalVisits = Math.log(this.visits);
        const ucbScore = (child) => {
            if (child.visits === 0) return Infinity;
            return (child.wins / child.visits) + 1.41 * Math.sqrt(logTotalVisits / child.visits);
        };
        return this.children.sort((a, b) => ucbScore(b) - ucbScore(a))[0];
    }
    expand() {
        const move = this.unexploredMoves.pop();
        const nextState = this.gameState.make_move(move);
        const childNode = new MCTS_Pro_Node(nextState, this, move);
        this.children.push(childNode);
        return childNode;
    }
    update(result) {
        this.visits += 1;
        this.wins += result;
        if (this.parent) {
            this.parent.update(result);
        }
    }
}

class MCTS_Pro_AI {
    constructor({ iterations = 1000 }) {
        this.iterations = iterations;
    }

    _create_determinized_state(currentState) {
        // --- 디버그 로그 ---
        // console.log("  [Debug] Creating a determinized state...");
        
        const determinizedState = currentState.clone();
        const rootPlayerIndex = currentState.turnIndex;
        const myHand = currentState.players[rootPlayerIndex].hand;
        const tableCards = currentState.tableCards.cards;

        const fullDeck = [];
        for (let i = 1; i <= 12; i++) { for (let j = 0; j < i; j++) fullDeck.push(i); }
        fullDeck.push(13, 13);

        const knownCards = [...myHand, ...tableCards];
        const unknownCardPool = fullDeck.filter(card => {
            const index = knownCards.indexOf(card);
            if (index > -1) {
                knownCards.splice(index, 1);
                return false;
            }
            return true;
        });

        for (let i = unknownCardPool.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [unknownCardPool[i], unknownCardPool[j]] = [unknownCardPool[j], unknownCardPool[i]];
        }

        let cardPoolIndex = 0;
        for (let i = 0; i < determinizedState.numPlayers; i++) {
            if (i !== rootPlayerIndex) {
                const otherPlayer = determinizedState.players[i];
                const handSize = otherPlayer.hand.length;
                otherPlayer.hand = unknownCardPool.slice(cardPoolIndex, cardPoolIndex + handSize);
                // --- 핵심 수정: 객체의 메서드를 호출하는 대신, 배열을 직접 정렬합니다. ---
                otherPlayer.hand.sort((a, b) => a - b);
                // --- 수정 종료 ---
                cardPoolIndex += handSize;
            }
        }
        
        // --- 디버그 로그 ---
        // console.log("  [Debug] Determinized state created successfully.");
        return determinizedState;
    }

    find_best_move(initialState) {
        // --- 디버그 로그 ---
        console.log(`%c[MCTS-Pro] Starting find_best_move for ${initialState.getCurrentPlayer().name}...`, 'color: cyan; font-weight: bold;');

        const rootNode = new MCTS_Pro_Node(initialState);
        const rootPlayerIndex = initialState.turnIndex;

        // MCTS가 계산을 시작하기 전에, 가능한 수가 pass밖에 없는지 확인
        if (rootNode.unexploredMoves.length === 1 && rootNode.unexploredMoves[0] === 'pass') {
            console.log("[MCTS-Pro] Only 'pass' is available. Skipping simulation.");
            return "pass";
        }

        for (let i = 0; i < this.iterations; i++) {
            let node = rootNode;
            
            // 1. Selection & 2. Expansion
            while (node.unexploredMoves.length === 0 && node.children.length > 0) {
                node = node.select_child();
            }
            if (node.unexploredMoves.length > 0) {
                node = node.expand();
            }

            // 3. Determinization
            const determinizedState = this._create_determinized_state(node.gameState);

            // 4. Simulation (Rollout)
            let simState = determinizedState;
            let safetyBreak = 0; // 무한 루프 방지
            while (!simState.gameOver && safetyBreak < 100) {
                const moves = simState.get_possible_moves();
                const randomMove = moves[Math.floor(Math.random() * moves.length)];
                simState = simState.make_move(randomMove);
                safetyBreak++;
            }

            // 5. Backpropagation
            const result = simState.winnerIndex === rootPlayerIndex ? 1 : 0;
            node.update(result);
        }

        // --- 디버그 로그 ---
        console.log("[MCTS-Pro] All iterations complete. Finding best move...");

        if (rootNode.children.length === 0) {
            console.log("[MCTS-Pro] No moves were explored. Defaulting to 'pass'.");
            return "pass";
        }
        
        const bestChild = rootNode.children.sort((a, b) => b.visits - a.visits)[0];
        
        // --- 디버그 로그 ---
        console.log(`%c[MCTS-Pro] Best move found:`, 'color: lightgreen; font-weight: bold;', bestChild.move);
        console.table(rootNode.children.map(c => ({ move: c.move, wins: c.wins, visits: c.visits, win_rate: (c.visits > 0 ? (c.wins / c.visits * 100).toFixed(2) + '%' : 'N/A') })));

        return bestChild.move;
    }
}
