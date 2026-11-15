export type Scenario = 'highway'|'curve'|'lane'|'avoid'|'urban';
export type Config = {name:string; scenario:Scenario; speed:number; leadSpeed:number; distance:number; decel:number; reaction:number; mu:number; radius:number; mass:number; wheelbase:number; steeringRatio:number; steeringLimit:number; brakeLimit:number; brakeGain:number; lateralLimit:number; duration:number; laneWidth:number; laneTime:number};
export const defaults:Config={name:'高速跟驰制动评估',scenario:'highway',speed:100,leadSpeed:60,distance:80,decel:5,reaction:0.8,mu:0.8,radius:250,mass:1800,wheelbase:2.8,steeringRatio:15,steeringLimit:540,brakeLimit:8,brakeGain:200,lateralLimit:3,duration:20,laneWidth:3.5,laneTime:5};
export const scenarioNames:Record<Scenario,string>={highway:'高速跟驰',curve:'弯道稳态',lane:'动态换道',avoid:'紧急避障',urban:'城市路口'};
export const templates:{id:Scenario;title:string;desc:string;tag:string;config:Partial<Config>}[]=[
 {id:'highway',title:'高速跟驰制动',desc:'评估高速跟驰下的制动响应与安全间距。',tag:'纵向控制',config:{...defaults}},
 {id:'curve',title:'弯道稳态行驶',desc:'检查侧向加速度、附着利用率与转向约束。',tag:'横向稳定',config:{name:'湿滑弯道稳定性评估',scenario:'curve',speed:70,mu:0.55,radius:150,duration:20}},
 {id:'lane',title:'高速动态换道',desc:'以五次多项式轨迹检查换道舒适性与横摆响应。',tag:'轨迹评估',config:{name:'高速单次换道评估',scenario:'lane',speed:90,mu:0.8,laneWidth:3.5,laneTime:5,duration:12}},
 {id:'avoid',title:'紧急避障制动',desc:'联合制动与侧向避让，评估轮胎附着裕度。',tag:'复合工况',config:{name:'紧急制动避障评估',scenario:'avoid',speed:60,leadSpeed:0,distance:45,decel:6,reaction:0.6,mu:0.7,laneTime:3.5,duration:12}},
 {id:'urban',title:'城市路口停车',desc:'分析城市低速下的停车距离与制动需求。',tag:'城市道路',config:{name:'城市路口停车评估',scenario:'urban',speed:40,leadSpeed:0,distance:30,decel:4,reaction:1,mu:0.8,duration:12}}
];
export const ranges:Record<string,[number,number]>={speed:[0,180],leadSpeed:[0,180],distance:[1,1000],decel:[0.1,12],reaction:[0,5],mu:[0.05,1.2],radius:[10,5000],mass:[500,5000],wheelbase:[1.5,5],steeringRatio:[5,30],steeringLimit:[90,1080],brakeLimit:[0.1,12],brakeGain:[50,1000],lateralLimit:[0.5,10],duration:[5,60],laneWidth:[2,5],laneTime:[2,12]};
export function validateConfig(c:Config){if(!c || typeof c.name!=='string' || !c.name.trim() || c.name.length>100)throw Error('请输入 1–100 字的工况名称');if(!Object.keys(scenarioNames).includes(c.scenario))throw Error('工况类型无效');for(const [k,[min,max]] of Object.entries(ranges)){const v=c[k as keyof Config];if(typeof v!=='number'||!Number.isFinite(v)||v<min||v>max)throw Error(`${k} 必须在 ${min}–${max} 范围内`);}return c;}
export type Sample={time:number;speed:number;distance:number;accel:number;lateral:number;yaw:number;steering:number;pressure:number;gap:number;utilization:number; y:number};
export type Finding={level:'pass'|'warn'|'fail';title:string;detail:string;source:string};
export function simulate(c:Config){
 validateConfig(c);const g=9.81,v0=c.speed/3.6, lead=c.leadSpeed/3.6;
 const braking=['highway','urban','avoid'].includes(c.scenario),changing=['lane','avoid'].includes(c.scenario);
 const effectiveDecel=Math.min(c.decel,c.brakeLimit,c.mu*g);
 const rows:Sample[]=[];let x=0,v=v0,minGap=c.distance,maxUtil=0,maxLat=0,maxSteer=0;
 for(let n=0;n<=Math.round(c.duration*10);n++){
  const t=n/10;let ax=0;
  if(braking && t>=c.reaction)ax=v>0?-effectiveDecel:0;
  if(n){const prevT=(n-1)/10,dt=t-prevT,active=braking?Math.max(0,Math.min(dt,t-Math.max(prevT,c.reaction))):0;const brakeTime=Math.min(active,v/effectiveDecel);x+=v*(dt-active)+v*brakeTime-0.5*effectiveDecel*brakeTime**2;v=Math.max(0,v-effectiveDecel*active);}
  ax=braking&&t>=c.reaction&&v>0?-effectiveDecel:0;
  const u=Math.max(0,Math.min(1,(t-c.reaction)/c.laneTime));
  const y=changing?c.laneWidth*(10*u**3-15*u**4+6*u**5):0;
  const lateral=c.scenario==='curve'?v*v/c.radius:changing&&t>=c.reaction&&t<=c.reaction+c.laneTime&&v>0?c.laneWidth/c.laneTime**2*(60*u-180*u*u+120*u**3):0;
  const yaw=v>0.1?lateral/v*180/Math.PI:0;
  const steering=v>0.1?Math.atan(c.wheelbase*lateral/(v*v))*180/Math.PI*c.steeringRatio:0;
  const pressure=Math.abs(ax)*c.mass/c.brakeGain;
  const gap=c.distance+(c.scenario==='highway'?lead*t:0)-x;
  const utilization=Math.hypot(ax,lateral)/(c.mu*g);
  minGap=Math.min(minGap,gap);maxUtil=Math.max(maxUtil,utilization);maxLat=Math.max(maxLat,Math.abs(lateral));maxSteer=Math.max(maxSteer,Math.abs(steering));
  rows.push({time:t,speed:v*3.6,distance:x,accel:ax,lateral,yaw,steering,pressure,gap,utilization,y});
 }
 const stoppingDistance=v0*c.reaction+v0*v0/(2*effectiveDecel),stopTime=c.reaction+v0/effectiveDecel;
 const safeCurveSpeed=Math.sqrt(Math.min(c.lateralLimit,c.mu*g)*c.radius)*3.6;
 const findings:Finding[]=[
  {level:maxUtil>1?'fail':maxUtil>0.85?'warn':'pass',title:'轮胎附着约束',detail:`峰值附着利用率 ${(maxUtil*100).toFixed(1)}%，依据纵横向加速度的摩擦圆近似。`,source:'KB-001'},
  {level:maxLat>c.lateralLimit?'warn':'pass',title:'侧向加速度',detail:`峰值 ${maxLat.toFixed(2)} m/s²，设置阈值 ${c.lateralLimit} m/s²（工程初始值，需标定）。`,source:'KB-002'},
  {level:maxSteer>c.steeringLimit?'fail':'pass',title:'转向物理约束',detail:`方向盘峰值 ${maxSteer.toFixed(1)}°，设置极限 ${c.steeringLimit}°。`,source:'KB-003'}
 ];
 if(braking){findings.push({level:minGap<=0?'fail':minGap<5?'warn':'pass',title:'制动与间距',detail:`仿真 ${c.duration} s 内最小间距 ${minGap.toFixed(1)} m；理论完全停车需 ${stoppingDistance.toFixed(1)} m / ${stopTime.toFixed(1)} s。前车按恒速运动，静态目标按固定障碍物计算。`,source:'KB-004'});if(c.decel>effectiveDecel+0.01)findings.push({level:'warn',title:'制动请求被约束',detail:`请求 ${c.decel} m/s²，受附着或底盘极限约束，实际采用 ${effectiveDecel.toFixed(2)} m/s²。`,source:'KB-001'});if(c.scenario==='avoid'&&stopTime<c.reaction+c.laneTime)findings.push({level:'warn',title:'避障轨迹适用性',detail:'车辆在规划换道结束前已停车。侧向轨迹仅用于需求估算，不代表实际可执行的避障路径。',source:'KB-005'});}
 const risk=findings.some(f=>f.level==='fail')?'高风险':findings.some(f=>f.level==='warn')?'需关注':'约束内';
 return {config:{...c},rows,findings,risk,effectiveDecel,stoppingDistance,stopTime,maxUtil,maxLat,maxSteer,minGap,safeCurveSpeed,braking};
}
export type Simulation=ReturnType<typeof simulate>;
export const knowledge=[
 {id:'KB-001',title:'附着与制动边界',category:'车辆动力学',body:'轮胎摩擦圆近似：√(ax²+ay²) ≤ μg。纯纵向减速度上限取附着极限 μg 与底盘减速度极限的较小值。质量相同时，附着系数下降会增加理论制动距离。联合制动转向超出摩擦圆时应降低车速或减小控制需求。本模型只评估请求，不闭环求解轮胎饱和。',basis:'基础质点力学；忽略载荷转移、坡度与轮胎非线性。'},
 {id:'KB-002',title:'弯道侧向稳定与舒适性',category:'横向稳定',body:'稳态圆周运动 ay = v²/R，v 单位为 m/s，R 单位为 m。建议速度由 v = √(min(ay阈值, μg)R) 估算。侧向加速度默认阈值 3 m/s² 是可配置工程初始值，不是法规限值。湿滑弯道应优先降低进入速度。',basis:'稳态圆周运动；不含侧偏角、横风与悬架模型。'},
 {id:'KB-003',title:'转向与横摆角速度',category:'底盘约束',body:'运动学单轨近似：横摆角速度 r = ay/v，前轮转角 δ = atan(Lay/v²)。方向盘转角 = δ × 转向传动比，统一输出 °。横摆输出 °/s。实车转向角应确认是方向盘角还是车轮角，再对标。',basis:'低侧偏运动学单轨模型；高动态时需动态模型验证。'},
 {id:'KB-004',title:'制动距离与响应时间',category:'纵向控制',body:'恒定减速度停车距离 s = v₀t反应 + v₀²/(2a)，停车时间 t = t反应 + v₀/a。高速跟驰采用前车恒速假设，最小间距必须结合全时序判断。制动压力用 F = ma 与可配置制动力增益 N/bar 估算，不代替液压系统模型。',basis:'水平路面恒减速；忽略空气阻力与执行器延迟变化。'},
 {id:'KB-005',title:'换道轨迹与紧急避障',category:'工况设计',body:'单次换道用五次多项式 y=W(10u³−15u⁴+6u⁵)，u=t/T。侧向加速度取轨迹对时间的二阶导数。缩短换道时长会显著增加横向需求。紧急避障叠加纵向制动时需联合检查摩擦圆，仅用于前期需求评估。',basis:'给定轨迹运动学需求；不包含规划器、控制器与碰撞几何。'},
 {id:'KB-006',title:'采集日志时间对齐与偏差',category:'数据对标',body:'采集日志先排序、剔除无效时间行、重复时间保留最后一行，以首个有效时间归零，再应用用户设置的时间偏移。通过线性插值在共同时间区间逐点比较，计算 MAE、RMSE 与最大绝对误差。没有覆盖的数据不补零、不外推。检查时间单位、传感器标定、方向盘/车轮角定义与制动增益。默认容差均为可编辑项目初始值。',basis:'V1.0 日志导入与对标协议 v1；需实车标定阈值。'}
];
