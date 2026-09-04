#import <Cocoa/Cocoa.h>

static NSString *Backend;
static NSString *ConfigPath;
@interface DailyApp : NSObject <NSApplicationDelegate,NSWindowDelegate>
@property NSWindow *window;
@property NSTextField *status,*detail;
@property NSButton *startButton,*sendButton,*cancelButton;
@property NSProgressIndicator *progress;
@property NSTask *task;
@property NSTimer *timer;
@property NSMutableData *buffer;
@property BOOL wantsShutdown,gotReceipt;
@property NSInteger remaining;
@end
@implementation DailyApp
- (BOOL)approved {
 NSData *d=[NSData dataWithContentsOfFile:ConfigPath];
 NSDictionary *j=d?[NSJSONSerialization JSONObjectWithData:d options:0 error:nil]:nil;
 return [j[@"approved"] isEqual:@YES];
}
- (NSTextField*)label:(NSString*)text frame:(NSRect)rect size:(CGFloat)size bold:(BOOL)bold {
 NSTextField *v=[NSTextField wrappingLabelWithString:text];v.frame=rect;
 v.font=bold?[NSFont boldSystemFontOfSize:size]:[NSFont systemFontOfSize:size];
 [self.window.contentView addSubview:v];return v;
}
- (NSButton*)button:(NSString*)title frame:(NSRect)rect action:(SEL)action {
 NSButton *b=[NSButton buttonWithTitle:title target:self action:action];b.frame=rect;b.bezelStyle=NSBezelStyleRounded;
 [self.window.contentView addSubview:b];return b;
}
- (void)applicationDidFinishLaunching:(NSNotification*)n {
 Backend=[NSBundle.mainBundle.resourcePath stringByAppendingPathComponent:@"backend"];
 NSString *home=NSProcessInfo.processInfo.environment[@"DAILY_SHUTDOWN_HOME"];
 if(!home)home=[NSHomeDirectory() stringByAppendingPathComponent:@"Library/Application Support/DailyShutdown"];
 ConfigPath=[home stringByAppendingPathComponent:@"config.json"];
 [NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];
 self.window=[[NSWindow alloc] initWithContentRect:NSMakeRect(0,0,620,440) styleMask:NSWindowStyleMaskTitled|NSWindowStyleMaskClosable|NSWindowStyleMaskMiniaturizable backing:NSBackingStoreBuffered defer:NO];
 self.window.title=@"日报后关机";self.window.releasedWhenClosed=NO;self.window.delegate=self;[self.window center];
 [self label:@"把今天收好，再关机。" frame:NSMakeRect(36,354,548,42) size:28 bold:YES];
 [self label:@"前 24 小时电脑记录与文件变化 → 中文日报与配图 → 本人微信" frame:NSMakeRect(36,307,548,38) size:14 bold:NO];
 self.status=[self label:@"准备就绪" frame:NSMakeRect(36,250,548,40) size:18 bold:YES];
 self.detail=[self label:@"微信接口确认接收后，倒计时 30 秒关机。\n发送失败会保留电脑运行；未保存文稿仍可能阻止系统关机。" frame:NSMakeRect(36,178,548,70) size:13 bold:NO];
 self.detail.textColor=NSColor.secondaryLabelColor;
 self.progress=[[NSProgressIndicator alloc] initWithFrame:NSMakeRect(36,162,548,8)];self.progress.style=NSProgressIndicatorStyleBar;self.progress.indeterminate=YES;self.progress.displayedWhenStopped=NO;[self.window.contentView addSubview:self.progress];
 self.startButton=[self button:@"生成日报并关机" frame:NSMakeRect(34,91,240,42) action:@selector(startShutdown:)];
 self.sendButton=[self button:@"仅发送日报，不关机" frame:NSMakeRect(288,91,240,42) action:@selector(startSend:)];
 self.cancelButton=[self button:@"取消" frame:NSMakeRect(484,34,100,30) action:@selector(cancel:)];self.cancelButton.enabled=NO;
 [self label:@"通常需要数分钟。运行时请保持联网。" frame:NSMakeRect(36,39,435,22) size:12 bold:NO];
 NSMenu *menu=[NSMenu new];NSMenuItem *item=[NSMenuItem new];[menu addItem:item];NSMenu *sub=[NSMenu new];[sub addItemWithTitle:@"退出日报后关机" action:@selector(terminate:) keyEquivalent:@"q"];item.submenu=sub;NSApp.mainMenu=menu;
 if(![self approved]) {self.status.stringValue=@"待确认数据处理授权";self.detail.stringValue=@"程序已准备好，尚未启用。请根据 README 完成本机配置并确认数据处理及本人微信发送授权，然后重新打开程序。";self.startButton.enabled=NO;self.sendButton.enabled=NO;}
 [self.window makeKeyAndOrderFront:nil];[NSApp activateIgnoringOtherApps:YES];
}
- (void)startShutdown:(id)sender {[self start:YES];}
- (void)startSend:(id)sender {[self start:NO];}
- (void)start:(BOOL)shutdown {
 if(self.task||self.timer||![self approved])return;
 self.wantsShutdown=shutdown;self.gotReceipt=NO;self.buffer=[NSMutableData new];
 self.startButton.enabled=NO;self.sendButton.enabled=NO;self.cancelButton.enabled=YES;
 self.status.stringValue=@"正在准备日报…";[self.progress startAnimation:nil];
 NSTask *task=[NSTask new];self.task=task;task.executableURL=[NSURL fileURLWithPath:[NSBundle.mainBundle objectForInfoDictionaryKey:@"PythonExecutable"]];
 task.arguments=@[[Backend stringByAppendingPathComponent:@"runner.py"],@"--mode",@"send"];
 NSMutableDictionary *env=[NSProcessInfo.processInfo.environment mutableCopy];env[@"PATH"]=@"/opt/homebrew/bin:/opt/homebrew/opt/node@24/bin:/usr/bin:/bin:/usr/sbin:/sbin";env[@"PYTHONUNBUFFERED"]=@"1";task.environment=env;
 NSPipe *pipe=[NSPipe pipe];task.standardOutput=pipe;task.standardError=pipe;
 __weak DailyApp *weak=self;
 pipe.fileHandleForReading.readabilityHandler=^(NSFileHandle *h){NSData *d=h.availableData;if(!d.length){h.readabilityHandler=nil;return;}dispatch_async(dispatch_get_main_queue(),^{[weak consume:d];});};
 task.terminationHandler=^(NSTask *t){int code=t.terminationStatus;dispatch_after(dispatch_time(DISPATCH_TIME_NOW,NSEC_PER_MSEC*250),dispatch_get_main_queue(),^{[weak finished:code];});};
 NSError *error=nil;if(![task launchAndReturnError:&error]){self.task=nil;[self fail:error.localizedDescription];}
}
- (void)consume:(NSData*)data {
 [self.buffer appendData:data];
 while(YES){const unsigned char *b=self.buffer.bytes;NSUInteger pos=0;while(pos<self.buffer.length&&b[pos]!=10)pos++;if(pos==self.buffer.length)break;
 NSData *line=[self.buffer subdataWithRange:NSMakeRange(0,pos)];[self.buffer replaceBytesInRange:NSMakeRange(0,pos+1) withBytes:NULL length:0];
 NSDictionary *j=[NSJSONSerialization JSONObjectWithData:line options:0 error:nil];if(![j isKindOfClass:NSDictionary.class])continue;
 NSString *stage=j[@"stage"];if(![stage isKindOfClass:NSString.class])continue;
 if([stage isEqual:@"sent"]){self.gotReceipt=YES;self.status.stringValue=@"微信接口已确认接收日报";}
 else if([stage isEqual:@"error"])[self fail:j[@"message"]?:@"未知错误"];
 else if([stage isEqual:@"cancelled"])self.status.stringValue=@"已取消；电脑保持运行";
 else self.status.stringValue=stage;
 }
}
- (void)finished:(int)code {
 self.task=nil;[self.progress stopAnimation:nil];
 if(code||!self.gotReceipt){self.startButton.enabled=[self approved];self.sendButton.enabled=[self approved];self.cancelButton.enabled=NO;if(![self.status.stringValue containsString:@"失败"]&&![self.status.stringValue containsString:@"取消"])self.status.stringValue=@"日报未完成，电脑保持运行";return;}
 if(self.wantsShutdown){self.remaining=30;[self tick:nil];self.timer=[NSTimer scheduledTimerWithTimeInterval:1 target:self selector:@selector(tick:) userInfo:nil repeats:YES];}
 else {self.status.stringValue=@"日报已发送；本次不关机";self.startButton.enabled=YES;self.sendButton.enabled=YES;self.cancelButton.enabled=NO;}
}
- (void)tick:(NSTimer*)timer {
 if(timer)self.remaining--;
 if(self.remaining<=0){[self.timer invalidate];self.timer=nil;self.cancelButton.enabled=NO;self.status.stringValue=@"正在请求 macOS 正常关机…";
  NSAppleScript *script=[[NSAppleScript alloc] initWithSource:@"tell application \"System Events\" to shut down"];NSDictionary *error=nil;[script executeAndReturnError:&error];if(error)[self fail:[NSString stringWithFormat:@"系统尚未关机：%@",error]];
 }else{self.status.stringValue=[NSString stringWithFormat:@"微信接口已接收 · %ld 秒后关机",(long)self.remaining];self.detail.stringValue=@"点击“取消”可保留电脑运行。接口接收不代表你已阅读。";}
}
- (void)cancel:(id)sender {
 self.wantsShutdown=NO;[self.timer invalidate];self.timer=nil;if(self.task.running)[self.task terminate];
 [self.progress stopAnimation:nil];self.status.stringValue=@"已取消；电脑保持运行";self.detail.stringValue=@"已经发送的消息不会撤回。若发送结果不确定，请先查看微信，避免重复发送。";self.cancelButton.enabled=NO;
 if(!self.task){self.startButton.enabled=[self approved];self.sendButton.enabled=[self approved];}
}
- (void)fail:(NSString*)message {self.wantsShutdown=NO;[self.timer invalidate];self.timer=nil;[self.progress stopAnimation:nil];self.status.stringValue=@"任务失败；电脑保持运行";self.detail.stringValue=message;self.startButton.enabled=[self approved];self.sendButton.enabled=[self approved];self.cancelButton.enabled=self.task!=nil;}
- (BOOL)windowShouldClose:(NSWindow*)sender {if(self.task||self.timer)[self cancel:nil];return YES;}
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication*)sender {return YES;}
- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication*)sender {if(self.task||self.timer)[self cancel:nil];return NSTerminateNow;}
@end
int main(int argc,const char **argv){@autoreleasepool {NSApplication *app=NSApplication.sharedApplication;DailyApp *delegate=[DailyApp new];app.delegate=delegate;[app run];}return 0;}
