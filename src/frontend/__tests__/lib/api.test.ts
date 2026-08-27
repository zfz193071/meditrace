import {
  diagnose,
  getHistory,
  verify,
  downloadReport,
  type DiagnoseRequest,
  type HistoryRecord,
} from '../../lib/api';

// Mock fetch
global.fetch = jest.fn();

describe('API Functions', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('diagnose', () => {
    it('should call diagnose API with correct parameters', async () => {
      const mockResponse = {
        diagnosisId: '123',
        suggestions: [
          {
            disease: '上呼吸道感染',
            confidence: 0.85,
            recommendations: ['血常规检查'],
          },
        ],
        disclaimer: '免责声明',
      };

      (fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      });

      const request: DiagnoseRequest = {
        symptoms: '头痛发热',
        userId: '0x1234567890123456789012345678901234567890',
      };

      const result = await diagnose(request);

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/diagnose',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(request),
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it('should throw error when API fails', async () => {
      (fetch as jest.Mock).mockResolvedValue({
        ok: false,
        json: async () => ({ detail: '诊断失败' }),
      });

      await expect(diagnose({ symptoms: 'test', userId: '0x123' })).rejects.toThrow('诊断失败');
    });
  });

  describe('getHistory', () => {
    it('should fetch history for a user', async () => {
      const mockRecords: HistoryRecord[] = [
        {
          diagnosisId: '123',
          timestamp: 1704067200,
          diseaseTypes: ['发热'],
          chainStatus: 'confirmed',
          ipfsCid: 'QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco',
        },
      ];

      (fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => ({ records: mockRecords }),
      });

      const result = await getHistory('0x1234567890123456789012345678901234567890');

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/history/0x1234567890123456789012345678901234567890'
      );
      expect(result.records).toEqual(mockRecords);
    });
  });

  describe('verify', () => {
    it('should verify a diagnosis record', async () => {
      const mockVerifyResponse = {
        isValid: true,
        chainRecord: {
          dataHash: '0xabcd1234',
          modelVersion: 'v1.0',
          timestamp: 1704067200,
          patient: '0x1234567890123456789012345678901234567890',
          ipfsCid: 'QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco',
        },
        ipfsCid: 'QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco',
      };

      (fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => mockVerifyResponse,
      });

      const result = await verify('123');

      expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/verify/123');
      expect(result.isValid).toBe(true);
      expect(result.chainRecord).toEqual(mockVerifyResponse.chainRecord);
    });
  });

  describe('downloadReport', () => {
    it('should download report as blob', async () => {
      const mockBlob = new Blob(['test pdf content'], { type: 'application/pdf' });

      (fetch as jest.Mock).mockResolvedValue({
        ok: true,
        blob: async () => mockBlob,
      });

      const result = await downloadReport('123');

      expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/report/123');
      expect(result).toBeInstanceOf(Blob);
    });

    it('should throw error when download fails', async () => {
      (fetch as jest.Mock).mockResolvedValue({
        ok: false,
        status: 404,
      });

      await expect(downloadReport('123')).rejects.toThrow('下载报告失败：404');
    });
  });
});
