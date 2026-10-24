from enum import Enum, IntEnum
#GiveAwardErrors = Enum('Success, WrongGender, NotGiftable, FullMailbox, FullAwardMailbox, AlreadyInMailbox, AlreadyInGiftQueue, AlreadyInOrderedQueue, AlreadyInCloset, AlreadyBeingWorn, AlreadyInAwardMailbox, AlreadyInThirtyMinuteQueue, AlreadyInMyPhrases, AlreadyKnowDoodleTraining, AlreadyRented, GenericAlreadyHaveError, UnknownError, UnknownToon, NonToon,')
class GiveAwardErrors(IntEnum):
    Success = 0
    WrongGender = 1
    NotGiftable = 2
    FullMailbox = 3
    FullAwardMailbox = 4
    AlreadyInMailbox = 5
    AlreadyInGiftQueue = 6
    AlreadyInOrderedQueue = 7
    AlreadyInCloset = 8
    AlreadyBeingWorn = 9
    AlreadyInAwardMailbox = 10
    AlreadyInThirtyMinuteQueue = 11
    AlreadyInMyPhrases = 12
    AlreadyKnowDoodleTraining = 13
    AlreadyRented = 14
    GenericAlreadyHaveError = 15
    UnknownError = 16
    UnknownToon = 17
    NonToon = 18
GiveAwardErrorStrings = {GiveAwardErrors.Success: 'success',
 GiveAwardErrors.WrongGender: 'wrong gender',
 GiveAwardErrors.NotGiftable: 'item is not giftable',
 GiveAwardErrors.FullMailbox: 'mailbox is full',
 GiveAwardErrors.FullAwardMailbox: 'award mailbox is full',
 GiveAwardErrors.AlreadyInMailbox: 'award already in mailbox.',
 GiveAwardErrors.AlreadyInGiftQueue: 'award already in gift queue.',
 GiveAwardErrors.AlreadyInOrderedQueue: 'award already in ordered queue.',
 GiveAwardErrors.AlreadyInCloset: 'award already in closet.',
 GiveAwardErrors.AlreadyBeingWorn: 'award already being worn.',
 GiveAwardErrors.AlreadyInAwardMailbox: 'award already in award mailbox',
 GiveAwardErrors.AlreadyInThirtyMinuteQueue: 'award already in 30 minute queue',
 GiveAwardErrors.AlreadyInMyPhrases: 'speed chat award already in my phrases',
 GiveAwardErrors.AlreadyKnowDoodleTraining: 'doodle training award already known',
 GiveAwardErrors.AlreadyRented: 'award is already rented',
 GiveAwardErrors.GenericAlreadyHaveError: 'generic-already-have error',
 GiveAwardErrors.UnknownError: 'unknown error',
 GiveAwardErrors.UnknownToon: 'toon not in database',
 GiveAwardErrors.NonToon: 'this is not a toon'}

