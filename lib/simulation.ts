import {quinticDemandExtrema} from './trajectory-extrema';
export type Scenario = 'highway'|'curve'|'lane'|'avoid'|'urban';
export type Config = {name:string; scenario:Scenario; speed:number; leadSpeed:number; distance:number; decel:number; reaction:number; mu:number; radius:number; mass:number; wheelbase:number; steeringRatio:number; steeringLimit:number; brakeLimit:number; brakeGain:number; lateralLimit:number; duration:number; laneWidth:number; laneTime:number};
export const defaults:Config={name:'高速跟驰制动评估',scenario:'highway',speed:100,leadSpeed:60,distance:80,decel:5,reaction:0.8,mu:0.8,radius:250,mass:1800,wheelbase:2.8,steeringRatio:15,steeringLimit:540,brakeLimit:8,brakeGain:200,lateralLimit:3,duration:20,laneWidth:3.5,laneTime:5};
export const scenarioNames:Record<Scenario,string>={highway:'高速跟驰',curve:'弯道稳态',lane:'动态换道',avoid:'紧急避障',urban:'城市路口'};
// Software applicability boundary for this simplified lateral-demand model.
// This is not a regulatory limit or a vehicle-independent minimum maneuver speed.
export const MIN_LATERAL_SPEED_KMH=5;
export const templates:{id:Scenario;title:string;desc:string;tag:string;config:Partial<Config>}[]=[
 {id:'highway',title:'高速跟驰制动',desc:'评估高速跟驰下的制动响应与安全间距。',tag:'纵向控制',config:{...defaults}},
 {id:'curve',title:'弯道稳态行驶',desc:'检查侧向加速度、附着利用率与转向约束。',tag:'横向稳定',config:{name:'湿滑弯道稳定性评估',scenario:'curve',speed:70,mu:0.55,radius:150,duration:20}},
 {id:'lane',title:'高速动态换道',desc:'以五次多项式轨迹检查换道舒适性与横摆响应。',tag:'轨迹评估',config:{name:'高速单次换道评估',scenario:'lane',speed:90,mu:0.8,laneWidth:3.5,laneTime:5,duration:12}},
 {id:'avoid',title:'紧急避障制动',desc:'联合制动与侧向避让，评估轮胎附着裕度。',tag:'复合工况',config:{name:'紧急制动避障评估',scenario:'avoid',speed:60,leadSpeed:0,distance:45,decel:6,reaction:0.6,mu:0.7,laneTime:3.5,duration:12}},
 {id:'urban',title:'城市路口停车',desc:'分析城市低速下的停车距离与制动需求。',tag:'城市道路',config:{name:'城市路口停车评估',scenario:'urban',speed:40,leadSpeed:0,distance:30,decel:4,reaction:1,mu:0.8,duration:12}}
];
export const ranges:Record<string,[number,number]>={speed:[0,180],leadSpeed:[0,180],distance:[1,1000],decel:[0.1,12],reaction:[0,5],mu:[0.05,1.2],radius:[10,5000],mass:[500,5000],wheelbase:[1.5,5],steeringRatio:[5,30],steeringLimit:[90,1080],brakeLimit:[0.1,12],brakeGain:[50,1000],lateralLimit:[0.5,10],duration:[5,60],laneWidth:[2,5],laneTime:[2,12]};
const parameterLabels:Record<string,string>={speed:'初始车速',leadSpeed:'前车车速',distance:'初始间距',decel:'期望减速度',reaction:'响应时间',mu:'路面附着系数',radius:'弯道半径',mass:'整车质量',wheelbase:'轴距',steeringRatio:'转向传动比',steeringLimit:'方向盘角极限',brakeLimit:'减速度极限',brakeGain:'制动力增益',lateralLimit:'侧向加速度阈值',duration:'仿真时长',laneWidth:'换道宽度',laneTime:'换道时长'};
export function validateConfig(c:Config){if(!c || typeof c.name!=='string' || !c.name.trim() || c.name.length>100)throw Error('请输入 1–100 字的工况名称');if(!Object.keys(scenarioNames).includes(c.scenario))throw Error('工况类型无效');for(const [k,[min,max]] of Object.entries(ranges)){const v=c[k as keyof Config];if(typeof v!=='number'||!Number.isFinite(v)||v<min||v>max)throw Error(`${parameterLabels[k]??k}必须在 ${min}–${max} 范围内`);}if(['lane','avoid'].includes(c.scenario)&&c.speed<MIN_LATERAL_SPEED_KMH)throw Error(`当前简化换道/避障模型需要初始车速至少 ${MIN_LATERAL_SPEED_KMH} km/h；更低速度不在模型适用范围内，不会用零转向代替未评估约束（此边界非法规限值）`);return c;}
export type Sample={time:number;speed:number;distance:number;accel:number;lateral:number;yaw:number;steering:number;pressure:number;gap:number;utilization:number; y:number};
export type Finding={level:'pass'|'warn'|'fail';title:string;detail:string;source:string};
export function simulate(c:Config){
 validateConfig(c);const g=9.81,v0=c.speed/3.6, lead=c.leadSpeed/3.6;
 const braking=['highway','urban','avoid'].includes(c.scenario),changing=['lane','avoid'].includes(c.scenario);
 const effectiveDecel=Math.min(c.decel,c.brakeLimit,c.mu*g);
 const stoppingDistance=v0*c.reaction+v0*v0/(2*effectiveDecel),stopTime=v0>0?c.reaction+v0/effectiveDecel:0;
 const rows:Sample[]=[];let x=0,v=v0,minGap=c.distance,maxUtil=0,maxLat=0,maxSteer=0,lowSpeedLateralDemand=false;
 for(let n=0;n<=Math.ceil(c.duration*10);n++){
  const t=Math.min(n/10,c.duration);let ax=0;
  if(braking && t>=c.reaction)ax=v>0?-effectiveDecel:0;
  if(n){const prevT=Math.min((n-1)/10,c.duration),dt=t-prevT,active=braking?Math.max(0,Math.min(dt,t-Math.max(prevT,c.reaction))):0;const brakeTime=Math.min(active,v/effectiveDecel);x+=v*(dt-active)+v*brakeTime-0.5*effectiveDecel*brakeTime**2;v=Math.max(0,v-effectiveDecel*active);}
  ax=braking&&t>=c.reaction&&v>0?-effectiveDecel:0;
  const trajectoryTime=braking?Math.min(t,stopTime):t;
  const u=Math.max(0,Math.min(1,(trajectoryTime-c.reaction)/c.laneTime));
  const y=changing?c.laneWidth*(10*u**3-15*u**4+6*u**5):0;
  const lateral=c.scenario==='curve'?v*v/c.radius:changing&&t>=c.reaction&&t<=c.reaction+c.laneTime&&v>0?c.laneWidth/c.laneTime**2*(60*u-180*u*u+120*u**3):0;
  if(changing&&v<MIN_LATERAL_SPEED_KMH/3.6&&Math.abs(lateral)>1e-9)lowSpeedLateralDemand=true;
  // A steady circle has finite geometric steering even at a small positive
  // speed. Avoid the generic lateral-demand division guard for this case.
  const yaw=c.scenario==='curve'?v/c.radius*180/Math.PI:v>0.1?lateral/v*180/Math.PI:0;
  const steering=c.scenario==='curve'&&v>0?Math.atan(c.wheelbase/c.radius)*180/Math.PI*c.steeringRatio:v>0.1?Math.atan(c.wheelbase*lateral/(v*v))*180/Math.PI*c.steeringRatio:0;
  const pressure=Math.abs(ax)*c.mass/c.brakeGain;
  const gap=c.distance+(c.scenario==='highway'?lead*t:0)-x;
  const utilization=Math.hypot(ax,lateral)/(c.mu*g);
  minGap=Math.min(minGap,gap);maxUtil=Math.max(maxUtil,utilization);maxLat=Math.max(maxLat,Math.abs(lateral));maxSteer=Math.max(maxSteer,Math.abs(steering));
  rows.push({time:t,speed:v*3.6,distance:x,accel:ax,lateral,yaw,steering,pressure,gap,utilization,y});
 }
 const sampledPeaks={lateral:maxLat,steering:maxSteer,utilization:maxUtil};
 const trajectoryExtrema=changing?quinticDemandExtrema({speedMps:v0,decel:effectiveDecel,braking,width:c.laneWidth,time:c.laneTime,reaction:c.reaction,duration:c.duration,wheelbase:c.wheelbase,steeringRatio:c.steeringRatio,minimumSpeedMps:MIN_LATERAL_SPEED_KMH/3.6}):null;
 if(trajectoryExtrema){
  maxLat=trajectoryExtrema.maxLateral;maxSteer=trajectoryExtrema.maxSteering;
  lowSpeedLateralDemand=lowSpeedLateralDemand||trajectoryExtrema.lowSpeedLateralDemand;
  if(trajectoryExtrema.activeEnd>0)maxUtil=Math.max(maxUtil,Math.hypot(braking?effectiveDecel:0,maxLat)/(c.mu*g));
 }
 // Keep the original 0.1 s row grid and log statistics contract. A brief
 // constant-deceleration pulse can fit entirely between two rows; retain its
 // analytical demand instead of treating unsampled pressure/force as zero.
 const maxPressure=braking&&v0>0?effectiveDecel*c.mass/c.brakeGain:0;
 const longitudinalUtilization=braking&&v0>0?effectiveDecel/(c.mu*g):0;
 maxUtil=Math.max(maxUtil,longitudinalUtilization);
 const brakingEventMissedByGrid=maxPressure>0&&!rows.some(r=>r.pressure>0);
 const closingSpeed=Math.max(0,v0-(c.scenario==='highway'?lead:0));
 const predictedMinGap=braking?c.distance-closingSpeed*c.reaction-closingSpeed**2/(2*effectiveDecel):null;
 const safeCurveSpeed=Math.sqrt(Math.min(c.lateralLimit,c.mu*g)*c.radius)*3.6;
 const findings:Finding[]=[
  {level:maxUtil>1?'fail':maxUtil>0.85?'warn':'pass',title:'轮胎附着约束',detail:`连续附着需求峰值利用率 ${(maxUtil*100).toFixed(1)}%，采用当前恒减速/给定轨迹的摩擦圆需求近似，不求解轮胎饱和后的运动。`,source:'KB-001'},
  {level:maxLat>c.lateralLimit?'warn':'pass',title:'侧向加速度',detail:`给定轨迹连续需求峰值 ${maxLat.toFixed(3)} m/s²，设置阈值 ${c.lateralLimit} m/s²（工程初始值，需标定）。`,source:'KB-002'},
  {level:maxSteer>c.steeringLimit?'fail':lowSpeedLateralDemand?'warn':'pass',title:'转向物理约束',detail:`适用速度域内连续方向盘需求峰值 ${maxSteer.toFixed(3)}°，设置极限 ${c.steeringLimit}°。${lowSpeedLateralDemand?'部分横向需求发生在模型最低适用速度以下，转向评估不完整，不能判定全部约束通过。':''}`,source:'KB-003'}
 ];
 if(braking){
  findings.push({level:predictedMinGap!<=0?'fail':predictedMinGap!<5?'warn':'pass',title:'完整制动过程预测',detail:`相同恒减速与目标运动假设下，全过程最小间距 ${predictedMinGap!.toFixed(1)} m；此项包含显示时间窗之外的解析预测。`,source:'KB-004'});
  if(v0>0&&c.duration<stopTime)findings.push({level:'warn',title:'仿真覆盖范围',detail:`显示窗口 ${c.duration} s 小于理论停车时间 ${stopTime.toFixed(2)} s。曲线尚未覆盖完整停车过程，请延长时长；完整制动预测单独列出。`,source:'KB-004'});
 }
 if(changing&&c.duration<c.reaction+c.laneTime)findings.push({level:'warn',title:'换道覆盖范围',detail:`换道计划在 ${(c.reaction+c.laneTime).toFixed(2)} s 结束，当前 ${c.duration} s 时间窗未覆盖完整轨迹。`,source:'KB-005'});
 if(lowSpeedLateralDemand)findings.push({level:'warn',title:'低速横向模型适用性',detail:`车辆在仍有横向需求时低于 ${MIN_LATERAL_SPEED_KMH} km/h。当前横向运动学需求模型不适用于该段，数值保护输出不代表实际横摆或转向为零；需低速专用模型重新验证。此最低速度是软件适用边界，非法规限值。`,source:'KB-005'});
 if(brakingEventMissedByGrid)findings.push({level:'warn',title:'制动事件采样覆盖',detail:`制动发生在 ${c.reaction.toFixed(3)}–${stopTime.toFixed(3)} s，未被 0.1 s 时序网格捕捉。曲线中的零压力或零加速度不代表没有制动需求；解析压力需求峰值 ${maxPressure.toFixed(2)} bar、纵向附着利用率 ${(longitudinalUtilization*100).toFixed(1)}%，压力增益仍需车型标定。`,source:'KB-004'});
 if(braking){findings.push({level:minGap<=0?'fail':minGap<5?'warn':'pass',title:'制动与间距',detail:`仿真 ${c.duration} s 内最小间距 ${minGap.toFixed(1)} m；理论完全停车需 ${stoppingDistance.toFixed(1)} m / ${stopTime.toFixed(1)} s。前车按恒速运动，静态目标按固定障碍物计算。`,source:'KB-004'});if(c.decel>effectiveDecel+0.01)findings.push({level:'warn',title:'制动请求被约束',detail:`请求 ${c.decel} m/s²，受附着或底盘极限约束，实际采用 ${effectiveDecel.toFixed(2)} m/s²。`,source:'KB-001'});if(c.scenario==='avoid'&&stopTime<c.reaction+c.laneTime)findings.push({level:'warn',title:'避障轨迹适用性',detail:'车辆在规划换道结束前已停车。侧向轨迹仅用于需求估算，不代表实际可执行的避障路径。',source:'KB-005'});}
 const risk=findings.some(f=>f.level==='fail')?'高风险':findings.some(f=>f.level==='warn')?'需关注':'约束内';
 return {config:{...c},rows,findings,risk,effectiveDecel,stoppingDistance,stopTime,maxUtil,maxPressure,maxLat,maxSteer,minGap,predictedMinGap,safeCurveSpeed,braking,sampling:{intervalS:0.1,brakingEventMissedByGrid,sampledPeaks},trajectoryExtrema,modelApplicability:{lateralMinimumSpeedKmh:MIN_LATERAL_SPEED_KMH,lowSpeedLateralDemand}};
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
