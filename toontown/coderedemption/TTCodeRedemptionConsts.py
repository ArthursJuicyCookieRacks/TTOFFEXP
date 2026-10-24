from enum import Enum, IntEnum
DefaultDbName = 'tt_code_redemption'
#RedeemErrors = Enum('Success, CodeDoesntExist, CodeIsInactive, CodeAlreadyRedeemed, AwardCouldntBeGiven, TooManyAttempts, SystemUnavailable, ')
class RedeemErrors(IntEnum):
    Success = 0
    CodeDoesntExist = 1
    CodeIsInactive = 2
    CodeAlreadyRedeemed = 3
    AwardCouldntBeGiven = 4
    TooManyAttempts = 5
    SystemUnavailable = 6
RedeemErrorStrings = {RedeemErrors.Success: 'Success',
 RedeemErrors.CodeDoesntExist: 'Invalid code',
 RedeemErrors.CodeIsInactive: 'Code is inactive',
 RedeemErrors.CodeAlreadyRedeemed: 'Code has already been redeemed',
 RedeemErrors.AwardCouldntBeGiven: 'Award could not be given',
 RedeemErrors.TooManyAttempts: 'Too many attempts, code ignored',
 RedeemErrors.SystemUnavailable: 'Code redemption is currently unavailable'}
MaxCustomCodeLen = config.ConfigVariableInt('tt-max-custom-code-len', 16).getValue()
