/**
 * 部署到 Sepolia 测试网
 * 
 * 使用前需要:
 * 1. 在 .env 中配置 SEPOLIA_RPC_URL 和 SEPOLIA_PRIVATE_KEY
 * 2. 确保钱包有足够的 Sepolia ETH (从 faucet 免费获取)
 */

const hre = require("hardhat");
require("dotenv").config({ path: "../.env" });

async function main() {
  console.log("🚀 开始部署到 Sepolia 测试网...");
  
  // 验证配置
  const sepoliaRpc = process.env.SEPOLIA_RPC_URL;
  const privateKey = process.env.SEPOLIA_PRIVATE_KEY;
  
  if (!sepoliaRpc || !privateKey) {
    throw new Error("请配置 SEPOLIA_RPC_URL 和 SEPOLIA_PRIVATE_KEY");
  }
  
  // 获取部署账户
  const [deployer] = await hre.ethers.getSigners();
  console.log(`📝 使用账户：${deployer.address}`);
  
  // 检查余额
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log(`💰 账户余额：${hre.ethers.formatEther(balance)} Sepolia ETH`);
  
  if (balance === 0n) {
    throw new Error("账户余额不足，请从 faucet 获取 Sepolia ETH");
  }
  
  // 部署合约
  console.log("\n🔨 正在部署 DiagnosisRecord 合约...");
  const DiagnosisRecord = await hre.ethers.getContractFactory("DiagnosisRecord");
  const diagnosisRecord = await DiagnosisRecord.deploy();
  await diagnosisRecord.waitForDeployment();
  
  const contractAddress = await diagnosisRecord.getAddress();
  console.log(`✅ 合约部署成功!`);
  console.log(`📍 合约地址：${contractAddress}`);
  
  // 验证部署
  console.log("\n🔍 验证部署...");
  const contract = await hre.ethers.getContractAt("DiagnosisRecord", contractAddress);
  const recordCount = await contract.getPatientRecordCount(deployer.address);
  console.log(`📊 初始记录数：${recordCount}`);
  
  // 保存部署信息
  const fs = require("fs");
  const deploymentInfo = {
    contract: "DiagnosisRecord",
    address: contractAddress,
    network: "sepolia",
    chainId: 11155111,
    deployer: deployer.address,
    timestamp: new Date().toISOString(),
    blockExplorer: `https://sepolia.etherscan.io/address/${contractAddress}`,
  };
  
  fs.writeFileSync(
    "deployment-sepolia.json",
    JSON.stringify(deploymentInfo, null, 2)
  );
  console.log("\n💾 部署信息已保存到 deployment-sepolia.json");
  
  // 输出使用信息
  console.log("\n" + "=".repeat(60));
  console.log("📋 下一步:");
  console.log("1. 在 Etherscan 验证合约:");
  console.log(`   https://sepolia.etherscan.io/address/${contractAddress}#code`);
  console.log("\n2. 更新后端配置:");
  console.log(`   CONTRACT_ADDRESS_SEPOLIA=${contractAddress}`);
  console.log("\n3. 查看区块浏览器:");
  console.log(`   ${deploymentInfo.blockExplorer}`);
  console.log("=".repeat(60));
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("❌ 部署失败:", error);
    process.exit(1);
  });
