"""
十六进制字符串与 bytes 转换工具函数

解决代码审查中发现的 Duplicated Code 和 Primitive Obsession 问题。
这些转换逻辑在 blockchain_client.py 和 main.py 中重复出现，
现在统一封装在此模块中。
"""

from typing import Union


def to_hex_str(data: Union[bytes, bytearray]) -> str:
    """
    将 bytes 转换为以 0x 开头的十六进制字符串
    
    Args:
        data: bytes 或 bytearray 数据
        
    Returns:
        以 0x 开头的十六进制字符串
        
    Examples:
        >>> to_hex_str(b'\\x01\\x02\\x03')
        '0x010203'
    """
    if isinstance(data, (bytes, bytearray)):
        return "0x" + data.hex()
    raise TypeError(f"Expected bytes or bytearray, got {type(data)}")


def from_hex_str(hex_str: str) -> bytes:
    """
    将以 0x 开头的十六进制字符串转换为 bytes
    
    Args:
        hex_str: 以 0x 开头的十六进制字符串
        
    Returns:
        bytes 数据
        
    Examples:
        >>> from_hex_str('0x010203')
        b'\\x01\\x02\\x03'
    """
    if isinstance(hex_str, str):
        # 移除 0x 前缀
        if hex_str.startswith("0x") or hex_str.startswith("0X"):
            hex_str = hex_str[2:]
        return bytes.fromhex(hex_str)
    raise TypeError(f"Expected str, got {type(hex_str)}")


def ensure_bytes32(hex_str: str) -> bytes:
    """
    确保输入转换为 32 字节的 bytes
    
    用于 Web3 智能合约调用，合约参数通常要求 bytes32 类型。
    如果输入短于 32 字节，会在右侧补零；如果长于 32 字节，会截断。
    
    Args:
        hex_str: 十六进制字符串 (可选带 0x 前缀)
        
    Returns:
        恰好 32 字节的 bytes
        
    Examples:
        >>> len(ensure_bytes32('0x0102'))
        32
        >>> len(ensure_bytes32('0102'))
        32
    """
    data = from_hex_str(hex_str)
    
    # 如果短于 32 字节，右侧补零
    if len(data) < 32:
        data = data.ljust(32, b'\\x00')
    # 如果长于 32 字节，截断
    elif len(data) > 32:
        data = data[:32]
    
    return data


def is_valid_hex_address(address: str) -> bool:
    """
    验证以太坊地址格式
    
    Args:
        address: 待验证的地址字符串
        
    Returns:
        如果地址格式有效返回 True，否则返回 False
        
    Examples:
        >>> is_valid_hex_address('0x262Ee58D3e7A782ceC68094a6DACb53D02Fa9d0B')
        True
        >>> is_valid_hex_address('0xInvalid')
        False
    """
    if not isinstance(address, str):
        return False
    
    # 检查是否以 0x 开头
    if not address.startswith("0x") and not address.startswith("0X"):
        return False
    
    # 检查长度 (0x + 40 个十六进制字符)
    if len(address) != 42:
        return False
    
    # 检查是否为有效的十六进制
    hex_part = address[2:]
    try:
        bytes.fromhex(hex_part)
        return True
    except ValueError:
        return False
