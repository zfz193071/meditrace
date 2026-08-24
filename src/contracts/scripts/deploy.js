const hre = require("hardhat");

async function main() {
  console.log("Deploying DiagnosisRecord contract...");

  const DiagnosisRecord = await hre.ethers.getContractFactory("DiagnosisRecord");
  const diagnosisRecord = await DiagnosisRecord.deploy();

  await diagnosisRecord.waitForDeployment();

  const contractAddress = await diagnosisRecord.getAddress();
  console.log(`DiagnosisRecord deployed to: ${contractAddress}`);

  // 保存部署信息
  const fs = require("fs");
  const deploymentInfo = {
    contract: "DiagnosisRecord",
    address: contractAddress,
    network: hre.network.name,
    timestamp: new Date().toISOString(),
  };

  fs.writeFileSync(
    "deployment.json",
    JSON.stringify(deploymentInfo, null, 2)
  );
  console.log("Deployment info saved to deployment.json");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
