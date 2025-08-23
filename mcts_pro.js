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
                otherPlayer.sortHand();
                cardPoolIndex += handSize;
            }
        }
        
        return determinizedState;
    }

    find_best_move(initialState) {
        const rootNode = new MCTS_Pro_Node(initialState);
        const rootPlayerIndex = initialState.turnIndex;

        for (let i = 0; i < this.iterations; i++) {
            let node = rootNode;
            
            while (node.unexploredMoves.length === 0 && node.children.length > 0) {
                node = node.select_child();
            }
            if (node.unexploredMoves.length > 0) {
                node = node.expand();
            }

            const determinizedState = this._create_determinized_state(node.gameState);

            let simState = determinizedState;
            while (!simState.gameOver) {
                const moves = simState.get_possible_moves();
                const randomMove = moves[Math.floor(Math.random() * moves.length)];
                simState = simState.make_move(randomMove);
            }

            const result = simState.winnerIndex === rootPlayerIndex ? 1 : 0;
            node.update(result);
        }

        if (rootNode.children.length === 0) return "pass";
        const bestChild = rootNode.children.sort((a, b) => b.visits - a.visits)[0];
        return bestChild.move;
    }
}
