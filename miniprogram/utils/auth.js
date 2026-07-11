/**
 * 微信登录 - code → openid → session
 */
const { request } = require('./request');

const login = () => {
  return new Promise((resolve, reject) => {
    wx.login({
      success: ({ code }) => {
        if (!code) {
          reject({ message: 'wx.login 未返回 code' });
          return;
        }
        request({
          url: '/auth/login',
          method: 'POST',
          data: { code }
        }).then(data => {
          wx.setStorageSync('access_token', data.access_token);
          wx.setStorageSync('refresh_token', data.refresh_token);
          resolve(data.user);
        }).catch(reject);
      },
      fail: (err) => reject({ message: 'wx.login 失败', detail: err })
    });
  });
};

const getUserProfile = () => {
  return new Promise((resolve, reject) => {
    wx.getUserProfile({
      desc: '用于展示头像和昵称',
      success: (res) => resolve(res.userInfo),
      fail: (err) => reject(err)
    });
  });
};

module.exports = { login, getUserProfile };
