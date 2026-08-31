const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("DiagnosisRecord", function () {
  let diagnosisRecord: any;
  let owner: any;
  let patient1: any;
  let patient2: any;

  beforeEach(async function () {
    [owner, patient1, patient2] = await ethers.getSigners();

    const DiagnosisRecord = await ethers.getContractFactory("DiagnosisRecord");
    diagnosisRecord = await DiagnosisRecord.deploy();
    await diagnosisRecord.waitForDeployment();
  });

  describe("recordDiagnosis", function () {
    it("Should record a diagnosis successfully", async function () {
      const dataHash = ethers.keccak256(ethers.toUtf8Bytes("test symptoms"));
      const modelVersion = "deepseek-v2.5-medkb-2024q1";
      const ipfsCid = "QmTest123456789";

      const tx = await diagnosisRecord
        .connect(patient1)
        .recordDiagnosis(dataHash, modelVersion, ipfsCid, patient1.address);

      const receipt = await tx.wait();
      
      // 从事件中获取 diagnosisId
      const event = receipt?.logs.find((log: any) => {
        try {
          const parsed = diagnosisRecord.interface.parseLog({
            topics: log.topics,
            data: log.data,
          });
          return parsed?.name === "DiagnosisRecorded";
        } catch {
          return false;
        }
      });
      
      let diagnosisId: string;
      if (event) {
        const parsed = diagnosisRecord.interface.parseLog({
          topics: event.topics,
          data: event.data,
        });
        diagnosisId = parsed?.args.diagnosisId;
      } else {
        // 如果无法从事件中获取，直接查询最后一个记录
        const recordCount = await diagnosisRecord.getPatientRecordCount(patient1.address);
        const patientRecords = await diagnosisRecord.getPatientRecords(patient1.address);
        diagnosisId = patientRecords[recordCount - 1];
      }

      const record = await diagnosisRecord.records(diagnosisId);

      expect(record.dataHash).to.equal(dataHash);
      expect(record.modelVersion).to.equal(modelVersion);
      expect(record.ipfsCid).to.equal(ipfsCid);
      expect(record.patient).to.equal(patient1.address);
    });

    it("Should emit DiagnosisRecorded event", async function () {
      const dataHash = ethers.keccak256(ethers.toUtf8Bytes("test symptoms"));
      const modelVersion = "deepseek-v2.5-medkb-2024q1";
      const ipfsCid = "QmTest123456789";

      await expect(
        diagnosisRecord
          .connect(patient1)
          .recordDiagnosis(dataHash, modelVersion, ipfsCid, patient1.address)
      )
        .to.emit(diagnosisRecord, "DiagnosisRecorded");
    });
  });

  describe("getPatientRecords", function () {
    it("Should return empty array for new patient", async function () {
      const records = await diagnosisRecord.getPatientRecords(patient1.address);
      expect(records.length).to.equal(0);
    });

    it("Should return all records for patient", async function () {
      const dataHash1 = ethers.keccak256(ethers.toUtf8Bytes("symptoms 1"));
      const dataHash2 = ethers.keccak256(ethers.toUtf8Bytes("symptoms 2"));
      const modelVersion = "deepseek-v2.5-medkb-2024q1";
      const ipfsCid = "QmTest123456789";

      await diagnosisRecord
        .connect(patient1)
        .recordDiagnosis(dataHash1, modelVersion, ipfsCid, patient1.address);
      await diagnosisRecord
        .connect(patient1)
        .recordDiagnosis(dataHash2, modelVersion, ipfsCid, patient1.address);

      const records = await diagnosisRecord.getPatientRecords(patient1.address);
      expect(records.length).to.equal(2);
    });
  });

  describe("getPatientRecordCount", function () {
    it("Should return correct count", async function () {
      const dataHash1 = ethers.keccak256(ethers.toUtf8Bytes("symptoms 1"));
      const dataHash2 = ethers.keccak256(ethers.toUtf8Bytes("symptoms 2"));
      const modelVersion = "deepseek-v2.5-medkb-2024q1";
      const ipfsCid = "QmTest123456789";

      expect(await diagnosisRecord.getPatientRecordCount(patient1.address)).to.equal(0);

      await diagnosisRecord
        .connect(patient1)
        .recordDiagnosis(dataHash1, modelVersion, ipfsCid, patient1.address);
      await diagnosisRecord
        .connect(patient1)
        .recordDiagnosis(dataHash2, modelVersion, ipfsCid, patient1.address);

      expect(await diagnosisRecord.getPatientRecordCount(patient1.address)).to.equal(2);
    });
  });
});
