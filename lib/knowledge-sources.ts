export const engineeringReferences:Record<string,{url:string;locator:string;note:string}>={
 'KB-001':{url:'https://cseweb.ucsd.edu/classes/sp19/cse291-d/Files/CSE291_14_VehicleDynamics.pdf',locator:'PDF 第 35 页：Friction Circle',note:'摩擦圆用于简化可行域判定；超限后的真实响应未在本模型中求解。'},
 'KB-002':{url:'https://publications.ri.cmu.edu/storage/publications/pub_files/2009/2/Automatic_Steering_Methods_for_Autonomous_Automobile_Path_Tracking.pdf',locator:'3.1 Kinematic Bicycle Model，正文第 18–20 页',note:'稳态圆周与无滑移运动学近似；舒适性阈值不是本资料给出的法规限值。'},
 'KB-003':{url:'https://publications.ri.cmu.edu/storage/publications/pub_files/2009/2/Automatic_Steering_Methods_for_Autonomous_Automobile_Path_Tracking.pdf',locator:'3.1，式 10；方向盘角还需车型转向比',note:'区分前轮角和方向盘角；高速明显侧偏时超出运动学近似适用范围。'},
 'KB-004':{url:'https://courses.grainger.illinois.edu/ece101/fa2025/lectures/101-024-autonomous-driving.pdf',locator:'PDF 第 23–26 页，制动距离；反应行程另以匀速运动推导',note:'常减速度解析式；制动压力由项目集总增益估算，尚未实车标定。'},
 'KB-005':{url:'https://github.com/AtsushiSakai/PythonRobotics/blob/master/PathPlanning/QuinticPolynomialsPlanner/quintic_polynomials_planner.py',locator:'QuinticPolynomial 初末六边界条件；MIT 许可',note:'使用独立线性方程求解器交叉验证轨迹，未复制其实现；平滑轨迹不等同于动态可执行性。'},
 'KB-006':{url:'https://github.com/commaai/comma2k19/blob/4c7f1a6e1957745beadc1def0e7225f559b09a2a/README.md#log-format',locator:'Log format；CAN/IMU 单位与设备启动秒时间戳',note:'平台清洗、插值和误差容差是项目协议；公开日志样例只用于导入验证。'}
};
