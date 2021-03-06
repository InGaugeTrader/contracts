ONE = 1;
TWO = 2;
MAX_FIXED_EXP_32 = 0x386bfdba29;


'''
    calculateBestPrecision 
    Predicts the highest precision which can be used in order to compute "base^exp" without exceeding 256 bits in any of the intermediate computations.
    Instead of calculating "base ^ exp", we calculate "e ^ (ln(base) * exp)".
    The value of ln(base) is represented with an integer slightly smaller than ln(base) * 2 ^ precision.
    The larger the precision is, the more accurately this value represents the real value.
    However, function fixedExpUnsafe(x), which calculates e ^ x, is limited to a maximum value of x.
    The limit depends on the precision (e.g, for precision = 32, the maximum value of x is MAX_FIXED_EXP_32).
    Hence before calling the 'power' function, we need to estimate an upper-bound for ln(base) * exponent.
    Of course, we should later assert that the value passed to fixedExpUnsafe is not larger than MAX_FIXED_EXP(precision).
    Due to this assertion (made in function fixedExp), functions calculateBestPrecision and fixedExp are tightly coupled.
    Note that the outcome of this function only affects the accuracy of the computation of "base ^ exp".
    Therefore, we do not need to assert that no intermediate result exceeds 256 bits (nor in this function, neither in any of the functions down the calling tree).
'''
def calculateBestPrecision(_baseN, _baseD, _expN, _expD):
    maxExp = MAX_FIXED_EXP_32;
    maxVal = lnUpperBound32(_baseN,_baseD) * _expN;
    for precision in range(0, 32, 2):
        if (maxExp < (maxVal << precision) / _expD):
            break;
        maxExp = (maxExp * 0xeb5ec5975959c565) >> (64-2);
    else:
        return 64-2;
    if (precision == 0):
        return 32;
    return precision+32-2;

'''
    @dev calculates (_baseN / _baseD) ^ (_expN / _expD)
    Returns result upshifted by precision

    This method is overflow-safe
''' 
def power(_baseN, _baseD, _expN, _expD, _precision):
    logbase = ln(_baseN, _baseD, _precision);
    # Not using safeDiv here, since safeDiv protects against
    # precision loss. It's unavoidable, however
    # Both `ln` and `fixedExp` are overflow-safe. 
    return fixedExp(safeMul(logbase, _expN) / _expD, _precision);

'''
    input range: 
        - numerator: [1, uint256_max >> precision]    
        - denominator: [1, uint256_max >> precision]
    output range:
        [0, 0x9b43d4f8d6]

    This method asserts outside of bounds
'''
def ln(_numerator, _denominator, _precision):
    # denominator > numerator: less than one yields negative values. Unsupported
    assert(_denominator <= _numerator);

    # log(1) is the lowest we can go
    assert(_denominator != 0 and _numerator != 0);

    # Upper bits are scaled off by precision
    MAX_VAL = ONE << (256 - _precision);
    assert(_numerator < MAX_VAL);
    assert(_denominator < MAX_VAL);

    return fixedLoge( (_numerator << _precision) / _denominator, _precision);

'''
    lnUpperBound32 
    Takes a rational number "baseN / baseD" as input.
    Returns an integer upper-bound of the natural logarithm of the input scaled by 2^32.
    We do this by calculating "UpperBound(log2(baseN / baseD)) * Ceiling(ln(2) * 2^32)".
    We calculate "UpperBound(log2(baseN / baseD))" as "Floor(log2((_baseN - 1) / _baseD)) + 1".
    For small values of "baseN / baseD", this sometimes yields a bad upper-bound approximation.
    We therefore cover these cases (and a few more) manually.
    Complexity is O(log(input bit-length)).
'''
def lnUpperBound32(_baseN, _baseD):
    assert(_baseN > _baseD);

    scaledBaseN = _baseN * 100000;
    if (scaledBaseN <= _baseD *  271828): # _baseN / _baseD < e^1 (floorLog2 will return 0 if _baseN / _baseD < 2)
        return 1 << 32;
    if (scaledBaseN <= _baseD *  738905): # _baseN / _baseD < e^2 (floorLog2 will return 1 if _baseN / _baseD < 4)
        return 2 << 32;
    if (scaledBaseN <= _baseD * 2008553): # _baseN / _baseD < e^3 (floorLog2 will return 2 if _baseN / _baseD < 8)
        return 3 << 32;

    return (floorLog2((_baseN - 1) / _baseD) + 1) * 0xb17217f8;

'''
    input range: 
        [0x100000000, uint256_max]
    output range:
        [0, 0x9b43d4f8d6]

    This method asserts outside of bounds

    Since `fixedLog2_min` output range is max `0xdfffffffff` 
    (40 bits, or 5 bytes), we can use a very large approximation
    for `ln(2)`. This one is used since it's the max accuracy 
    of Python `ln(2)`

    0xb17217f7d1cf78 = ln(2) * (1 << 56)
'''
def fixedLoge(_x, _precision):
    #Cannot represent negative numbers (below 1)
    assert(_x >= ONE << _precision);

    log2 = fixedLog2(_x, _precision);
    return (log2 * 0xb17217f7d1cf78) >> 56;

'''
    Returns log2(x >> 32) << 32 [1]
    So x is assumed to be already upshifted 32 bits, and 
    the result is also upshifted 32 bits. 
    
    [1] The function returns a number which is lower than the 
    actual value

    input-range : 
        [0x100000000, uint256_max]
    output-range: 
        [0,0xdfffffffff]

    This method asserts outside of bounds

'''
def fixedLog2(_x, _precision):
    fixedOne = ONE << _precision;
    fixedTwo = TWO << _precision;

    # Numbers below 1 are negative. 
    assert( _x >= fixedOne);

    hi = 0;
    while (_x >= fixedTwo):
        _x >>= 1;
        hi += fixedOne;

    for i in range(_precision):
        _x = (_x * _x) / fixedOne;
        if (_x >= fixedTwo):
            _x >>= 1;
            hi += ONE << (_precision - 1 - i);

    return hi;

'''
    floorLog2
    Takes a natural number (n) as input.
    Returns the largest integer smaller than or equal to the binary logarithm of the input.
    Complexity is O(log(input bit-length)).
'''
def floorLog2(_n):
    t = 0;
    for s in [1<<(8-1-k) for k in range(8)]:
        if (_n >= (ONE << s)):
            _n >>= s;
            t |= s;

    return t;

'''
    fixedExp is a 'protected' version of `fixedExpUnsafe`, which asserts instead of overflows.
    The maximum value which can be passed to fixedExpUnsafe depends on the precision used.
    The following array maps each precision between 0 and 63 to the maximum value permitted:
    maxExpArray = {
        0xc1               ,0x17a              ,0x2e5              ,0x5ab              ,
        0xb1b              ,0x15bf             ,0x2a0c             ,0x50a2             ,
        0x9aa2             ,0x1288c            ,0x238b2            ,0x4429a            ,
        0x82b78            ,0xfaadc            ,0x1e0bb8           ,0x399e96           ,
        0x6e7f88           ,0xd3e7a3           ,0x1965fea          ,0x30b5057          ,
        0x5d681f3          ,0xb320d03          ,0x15784a40         ,0x292c5bdd         ,
        0x4ef57b9b         ,0x976bd995         ,0x122624e32        ,0x22ce03cd5        ,
        0x42beef808        ,0x7ffffffff        ,0xf577eded5        ,0x1d6bd8b2eb       ,
        0x386bfdba29       ,0x6c3390ecc8       ,0xcf8014760f       ,0x18ded91f0e7      ,
        0x2fb1d8fe082      ,0x5b771955b36      ,0xaf67a93bb50      ,0x15060c256cb2     ,
        0x285145f31ae5     ,0x4d5156639708     ,0x944620b0e70e     ,0x11c592761c666    ,
        0x2214d10d014ea    ,0x415bc6d6fb7dd    ,0x7d56e76777fc5    ,0xf05dc6b27edad    ,
        0x1ccf4b44bb4820   ,0x373fc456c53bb7   ,0x69f3d1c921891c   ,0xcb2ff529eb71e4   ,
        0x185a82b87b72e95  ,0x2eb40f9f620fda6  ,0x5990681d961a1ea  ,0xabc25204e02828d  ,
        0x14962dee9dc97640 ,0x277abdcdab07d5a7 ,0x4bb5ecca963d54ab ,0x9131271922eaa606 ,
        0x116701e6ab0cd188d,0x215f77c045fbe8856,0x3ffffffffffffffff,0x7abbf6f6abb9d087f,
    };
    Since we cannot use an array of constants, we need to approximate the maximum value dynamically.
    For a precision of 32, the maximum value permitted is MAX_FIXED_EXP_32.
    For each additional precision unit, the maximum value permitted increases by approximately 1.9.
    So in order to calculate it, we need to multiply MAX_FIXED_EXP_32 by 1.9 for every additional precision unit.
    And in order to optimize for speed, we multiply MAX_FIXED_EXP_32 by 1.9^2 for every 2 additional precision units.
    Hence the general function for mapping a given precision to the maximum value permitted is:
    - precision = [32, 34, 36, ..., 62]
    - MaxFixedExp(precision) = MAX_FIXED_EXP_32 * 3.61 ^ (precision / 2 - 16)
    Since we cannot use non-integers, we do MAX_FIXED_EXP_32 * 361 ^ (precision / 2 - 16) / 100 ^ (precision / 2 - 16).
    But there is a better approximation, because this "1.9" factor in fact extends beyond a single decimal digit.
    So instead, we use 0xeb5ec5975959c565 / 0x4000000000000000, which yields maximum values quite close to real ones:
    maxExpArray = {
        -------------------,-------------------,-------------------,-------------------,
        -------------------,-------------------,-------------------,-------------------,
        -------------------,-------------------,-------------------,-------------------,
        -------------------,-------------------,-------------------,-------------------,
        -------------------,-------------------,-------------------,-------------------,
        -------------------,-------------------,-------------------,-------------------,
        -------------------,-------------------,-------------------,-------------------,
        -------------------,-------------------,-------------------,-------------------,
        0x386bfdba29       ,-------------------,0xcf8014760e       ,-------------------,
        0x2fb1d8fe07b      ,-------------------,0xaf67a93bb37      ,-------------------,
        0x285145f31a8f     ,-------------------,0x944620b0e5ee     ,-------------------,
        0x2214d10d0112e    ,-------------------,0x7d56e7677738e    ,-------------------,
        0x1ccf4b44bb20d0   ,-------------------,0x69f3d1c9210d27   ,-------------------,
        0x185a82b87b5b294  ,-------------------,0x5990681d95d4371  ,-------------------,
        0x14962dee9dbd672b ,-------------------,0x4bb5ecca961fb9bf ,-------------------,
        0x116701e6ab0967080,-------------------,0x3fffffffffffe6652,-------------------,
    };
'''
def fixedExp(_x, _precision):
    maxExp = MAX_FIXED_EXP_32;
    for p in range(32, _precision, 2):
        maxExp = (maxExp * 0xeb5ec5975959c565) >> (64-2);
    
    assert(_x <= maxExp);
    return fixedExpUnsafe(_x, _precision);

'''
    fixedExp 
    Calculates e ^ x according to maclauren summation:

    e^x = 1 + x + x ^ 2 / 2!...+ x ^ n / n!

    and returns e ^ (x >> 32) << 32, that is, upshifted for accuracy

    Input range:
        - Function ok at    <= 242329958953 
        - Function fails at >= 242329958954

    This method is is visible for testcases, but not meant for direct use. 

    The values in this method been generated via the following python snippet: 

    def calculateFactorials():
        """Method to print out the factorials for fixedExp"""

        ni = []
        ni.append(295232799039604140847618609643520000000) # 34!
        ITERATIONS = 34
        for n in range(1, ITERATIONS, 1) :
            ni.append(math.floor(ni[n - 1] / n))
        print( "\n        ".join(["xi = (xi * _x) >> _precision;\n        res += xi * %s;" % hex(int(x)) for x in ni]))

'''
def fixedExpUnsafe(_x, _precision):
    xi = _x;
    res = (0xde1bc4d19efcac82445da75b00000000) << _precision;

    res += xi * 0xde1bc4d19efcac82445da75b00000000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x6f0de268cf7e5641222ed3ad80000000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x2504a0cd9a7f7215b60f9be480000000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x9412833669fdc856d83e6f920000000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x1d9d4d714865f4de2b3fafea0000000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x4ef8ce836bba8cfb1dff2a70000000;
    xi = (xi * _x) >> _precision;
    res += xi * 0xb481d807d1aa66d04490610000000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x16903b00fa354cda08920c2000000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x281cdaac677b334ab9e732000000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x402e2aad725eb8778fd85000000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x5d5a6c9f31fe2396a2af000000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x7c7890d442a82f73839400000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x9931ed54034526b58e400000;
    xi = (xi * _x) >> _precision;
    res += xi * 0xaf147cf24ce150cf7e00000;
    xi = (xi * _x) >> _precision;
    res += xi * 0xbac08546b867cdaa200000;
    xi = (xi * _x) >> _precision;
    res += xi * 0xbac08546b867cdaa20000;
    xi = (xi * _x) >> _precision;
    res += xi * 0xafc441338061b2820000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x9c3cabbc0056d790000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x839168328705c30000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x694120286c049c000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x50319e98b3d2c000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x3a52a1e36b82000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x289286e0fce000;
    xi = (xi * _x) >> _precision;
    res += xi * 0x1b0c59eb53400;
    xi = (xi * _x) >> _precision;
    res += xi * 0x114f95b55400;
    xi = (xi * _x) >> _precision;
    res += xi * 0xaa7210d200;
    xi = (xi * _x) >> _precision;
    res += xi * 0x650139600;
    xi = (xi * _x) >> _precision;
    res += xi * 0x39b78e80;
    xi = (xi * _x) >> _precision;
    res += xi * 0x1fd8080;
    xi = (xi * _x) >> _precision;
    res += xi * 0x10fbc0;
    xi = (xi * _x) >> _precision;
    res += xi * 0x8c40;
    xi = (xi * _x) >> _precision;
    res += xi * 0x462;
    xi = (xi * _x) >> _precision;
    res += xi * 0x22;

    return res / 0xde1bc4d19efcac82445da75b00000000;


def safeMul(x,y):
    assert(x * y < (1 << 256))
    return x * y
