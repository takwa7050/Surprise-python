from algo import *

class AlgoUsingMeanDiff(Algo):
    """Astract class for algorithms using the mean difference between the
    ratings of two users/items"""
    def __init__(self, trainingData, itemBased=False, **kwargs):
        super().__init__(trainingData, itemBased=itemBased, **kwargs)

        print("computing mean differences between users...")
        self.meanDiff = np.zeros((self.nX, self.nX))
        self.meanDiffWeight = np.zeros((self.nX, self.nX))

        diffs = defaultdict(int)  # sum (r_ui - r_vi) for common items
        freq = defaultdict(int)   # number common items

        for y, yRatings in self.yr.items():
            for (xi, r1), (xj, r2) in combinations(yRatings, 2):
                diffs[xi, xj] += (r1 - r2)
                freq[xi, xj] += 1

        for xi in range(self.nX):
            for xj in range(xi, self.nX):
                if freq[xi, xj]:
                    self.meanDiff[xi, xj] = diffs[xi, xj] / freq[xi, xj]
                    self.meanDiffWeight[xi, xj] = (
                        1. / (np.std(diffs[xi, xj]) + 1))

                self.meanDiff[xj, xi] = -self.meanDiff[xi, xj]
                self.meanDiffWeight[xj, xi] = self.meanDiffWeight[xi, xj]

class AlgoCloneBruteforce(Algo):
    """Algo based on cloning, quite rough and straightforward:
    pred(r_xy) = mean(r_x'y + k) for all x' that are k-clone of x
    """

    def __init__(self, trainingData, itemBased=False, **kwargs):
        super().__init__(trainingData, itemBased=itemBased)

        self.infos['name'] = 'AlgoClonBruteForce'

    def isClone(self, ra, rb, k):
        """ return True if xa (with ratings ra) is a k-clone of xb (with
        ratings rb)

            condition is sum(|(r_ai - r_bi) - k|) <= |I_ab| where |I_ab| is the
            number of common ys
        """
        diffs = [xai - xbi for (xai, xbi) in zip(ra, rb)]
        sigma = sum(abs(diff - k) for diff in diffs)
        return sigma <= len(diffs)

    def estimate(self, u0, i0):
        x0, y0 = self.getx0y0(u0, i0)

        candidates = []
        for (x, rx) in self.yr[y0]: # for ALL xs that have rated y0
            # find common ratings between x0 and x
            commonRatings = [(self.rm[x0, y], self.rm[x, y]) for (y, _) in self.xr[x0] if self.rm[x, y] > 0]
            if not commonRatings: continue
            ra, rb = zip(*commonRatings)
            for k in range(-4, 5):
                if self.isClone(ra, rb, k):
                    candidates.append(rx + k)

        if candidates:
            est = np.mean(candidates)
            return est
        else:
            raise PredictionImpossible

class AlgoCloneMeanDiff(AlgoUsingMeanDiff):
    """Algo based on cloning:

    pred(r_xy) = av_mean(r_x'y + meanDiff(x', x)) for all x' having rated y.
    The mean is weighted by how 'steady' is the meanDiff
    """

    def __init__(self, trainingData, itemBased=False, **kargs):
        super().__init__(trainingData, itemBased=itemBased)

        self.infos['name'] = 'AlgoCloneMeanDiff'

    def estimate(self, u0, i0):
        x0, y0 = self.getx0y0(u0, i0)

        candidates = []
        weights = []
        for (x, rx) in self.yr[y0]: # for ALL xs that have rated y0

            weight = self.meanDiffWeight[x0, x]
            if weight: # if x and x0 have ys in common
                candidates.append(rx + self.meanDiff[x0, x])
                weights.append(weight)

        if candidates:
            est = np.average(candidates, weights=weights)
            return est
        else:
            raise PredictionImpossible

class AlgoCloneKNNMeanDiff(AlgoUsingMeanDiff, AlgoUsingSim):
    """Algo based on cloning:

    pred(r_xy) = av_mean(rx'y + meanDiff(x', x)) for all x' that are "close" to
    x. the term "close" can take into account constant differences other than 0
    using an appropriate similarity measure
    """

    def __init__(self, trainingData, itemBased=False, sim='MSDClone', k=40, **kwargs):
        super().__init__(trainingData, itemBased=itemBased, sim=sim)

        self.infos['name'] = 'AlgoCloneKNNMeanDiff'

        self.k = k

        self.infos['params']['similarity measure'] = sim
        self.infos['params']['k'] = self.k

    def estimate(self, u0, i0):
        x0, y0 = self.getx0y0(u0, i0)

        neighbors = [(x, self.simMat[x0, x], r) for (x, r) in self.yr[y0]]

        if not neighbors:
            raise PredictionImpossible

        # sort neighbors by similarity
        neighbors = sorted(neighbors, key=lambda x:x[1], reverse=True)

        # compute weighted average
        sumSim = sumRatings = 0
        for (nb, sim, r) in neighbors[:self.k]:
            if sim > 0:
                sumSim += sim
                sumRatings += sim * (r + self.meanDiff[x0, nb])

        try:
            est = sumRatings / sumSim
        except ZeroDivisionError:
            raise PredictionImpossible

        return est