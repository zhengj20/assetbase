from app.models.archive import (
    AssCategory,
    AssOffice,
    AssSpace,
    AssSupplier,
    AssWarehouse,
)
from app.models.asset import (
    AssAsset,
    AssAssetGroup,
    AssAssetImage,
    AssAssetLog,
)
from app.models.check import (
    AssCheckItem,
    AssCheckTask,
    AssDepreciation,
    WfBizApprovalConfig,
    WfDefinition,
    WfInstance,
    WfTask,
)
from app.models.doc import (
    AssPurchaseApply,
    AssPurchaseApplyItem,
    AssScrap,
    AssScrapItem,
    AssStockIn,
    AssStockInItem,
    AssStockOut,
    AssStockOutItem,
    AssTransfer,
    AssTransferItem,
)
from app.models.consumable import (
    ConInbound,
    ConInboundItem,
    ConIssue,
    ConIssueItem,
    ConItem,
    ConPurchase,
    ConPurchaseItem,
    ConStock,
)
from app.models.sys import (
    SysCodeSeq,
    SysDictData,
    SysDictType,
    SysFile,
    SysMenu,
    SysMessage,
    SysOperationLog,
    SysOrg,
    SysRole,
    SysRoleMenu,
    SysUser,
    SysUserRole,
)

__all__ = [
    # 系统管理域
    "SysOrg", "SysUser", "SysRole", "SysUserRole", "SysMenu", "SysRoleMenu",
    "SysDictType", "SysDictData", "SysOperationLog", "SysMessage", "SysFile",
    "SysCodeSeq", "SysWorkRecord",
    # 基础档案域
    "AssCategory", "AssSupplier", "AssSpace", "AssWarehouse", "AssOffice",
    # 资产核心域
    "AssAsset", "AssAssetGroup", "AssAssetLog", "AssAssetImage",
    # 业务单据域
    "AssPurchaseApply", "AssPurchaseApplyItem",
    "AssStockIn", "AssStockInItem",
    "AssStockOut", "AssStockOutItem",
    "AssTransfer", "AssTransferItem",
    "AssScrap", "AssScrapItem",
    # 易耗品域（库存型）
    "ConItem", "ConStock", "ConPurchase", "ConPurchaseItem",
    "ConInbound", "ConInboundItem", "ConIssue", "ConIssueItem",
    # 盘点折旧域 + 工作流域
    "AssCheckTask", "AssCheckItem", "AssDepreciation",
    "WfDefinition", "WfInstance", "WfTask", "WfBizApprovalConfig",
]
