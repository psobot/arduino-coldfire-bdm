class ControlRegisters:
    CACR = 0x0002
    CacheControlRegister = 0x0002

    ACR0 = 0x0004
    AccessControlRegister0 = 0x0004

    ACR1 = 0x0005
    AccessControlRegister1 = 0x0005

    VBR = 0x801
    VectorBaseRegister = 0x801

    MACSR = 0x804
    MACStatusRegister = 0x804

    MASK = 0x805
    MACMaskRegister = 0x805

    ACC = 0x806
    MACAccumulator = 0x806

    SR = 0x80E
    StatusRegister = 0x80E

    PC = 0x80F
    ProgramCounter = 0x80F

    RAMBAR = 0xC04
    RAMBaseAddressRegister = 0xC04

    MBAR = 0xC0F
    ModuleBaseAddressRegister = 0xC0F
