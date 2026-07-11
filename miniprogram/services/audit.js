/**
 * 审计服务 - 解析策略 / 提交审计 / 查询结果
 */
const { request } = require('../utils/request');

const parseStrategy = (description) => {
  return request({
    url: '/audit/parse',
    method: 'POST',
    data: { description }
  });
};

const submitAudit = (spec) => {
  return request({
    url: '/audit/submit',
    method: 'POST',
    data: { spec }
  });
};

const getAuditResult = (jobId) => {
  return request({
    url: `/audit/result/${jobId}`,
    method: 'GET'
  });
};

const listAuditHistory = (limit = 20) => {
  return request({
    url: `/audit/history?limit=${limit}`,
    method: 'GET'
  });
};

module.exports = {
  parseStrategy,
  submitAudit,
  getAuditResult,
  listAuditHistory
};
