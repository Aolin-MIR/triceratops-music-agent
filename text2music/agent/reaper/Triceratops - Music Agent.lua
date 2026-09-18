-- @description Triceratops: Music Agent
-- @version 7.0
local ROOT="E:\\text2score\\text2music\\artifacts\\agent_runs"
local DIALOG=reaper.GetResourcePath().."\\Scripts\\Triceratops\\TriceratopsComposerLauncher.ps1"
local PROMPT_RESULT=ROOT.."\\reaper_prompt_result.txt"
local imported,rejected,mouse_down,prepared_run,pending_prompt="","","",false,""
local button_motion={}
local arrangement_scroll,arrangement_dragging,arrangement_drag_offset=0,false,0
local FONT_SCALE=1.42
local panel_opened=reaper.time_precise()

local function read(path)local f=io.open(path,"r");if not f then return""end;local s=f:read("*a");f:close();return s end
local function exists(path)local f=io.open(path,"r");if not f then return false end;f:close();return true end
local function value(s,k)return s:match(k..": ([^\r\n]+)")or""end
local function c(r,g,b,a)gfx.set(r,g,b,a or 1)end
local function card(x,y,w,h,r,g,b,rad)c(r,g,b);gfx.roundrect(x,y,w,h,rad or 16,1)end
local function font(sz,bold)gfx.setfont(1,"Segoe UI",math.floor(sz*FONT_SCALE+.5),"b")end
local function text(s,x,y,sz,r,g,b,bold)font(sz,true);c(.025,.02,.015);gfx.x=x;gfx.y=y;gfx.drawstr(s)end
local function clipped(s,n)s=(s or ""):gsub("\r",""):gsub("\n"," ");return #s>n and s:sub(1,n-3).."..."or s end
local function active(s)return s=="analyzing_audio"or s=="planning"or s=="loading_model"or s=="sampling"or s=="verifying"or s=="converting"or s=="correcting"end
local function project_has_midi()for i=0,reaper.CountMediaItems(0)-1 do local t=reaper.GetActiveTake(reaper.GetMediaItem(0,i));if t and reaper.TakeIsMIDI(t)then return true end end;return false end
local function prepare_tracks(plan_path,run)
 if prepared_run==run or project_has_midi()then return end
 local plan=read(plan_path);local list=plan:match("Instruments:%s*([^\r\n]+)")or"Electric Guitar, Electric Bass, Drumset";local i=reaper.CountTracks(0)
 for item in list:gmatch("[^,]+")do local name=item:match("^%s*(.-)%s*$");if name~=""then reaper.InsertTrackAtIndex(i,true);reaper.GetSetMediaTrackInfo_String(reaper.GetTrack(0,i),"P_NAME",name,true);i=i+1 end end
 prepared_run=run;reaper.TrackList_AdjustWindows(false)
end
local function capture_context()
 local cursor=tonumber(reaper.GetCursorPosition())or 0;local t1,t2,t3,t4=reaper.TimeMap_GetTimeSigAtTime(0,cursor)
 local num,den,bpm;if t4~=nil then num,den,bpm=t2,t3,t4 else num,den,bpm=t1,t2,t3 end
 num=tonumber(num)or 4;den=tonumber(den)or 4;bpm=tonumber(bpm)or 120
 local rate=tonumber(reaper.GetSetProjectInfo(0,"PROJECT_SRATE",0,false))or 0;local a,b=reaper.GetSet_LoopTimeRange(false,false,0,0,false);a=tonumber(a)or 0;b=tonumber(b)or 0;local tracks={}
 for i=0,reaper.CountTracks(0)-1 do
  local tr=reaper.GetTrack(0,i);local _,n=reaper.GetTrackName(tr,"");local midi_items,audio_items,sources=0,0,{}
  for j=0,reaper.CountTrackMediaItems(tr)-1 do local item=reaper.GetTrackMediaItem(tr,j);local take=reaper.GetActiveTake(item);if take then
   if reaper.TakeIsMIDI(take)then midi_items=midi_items+1 else audio_items=audio_items+1;local source=reaper.GetMediaItemTake_Source(take);local _,path=reaper.GetMediaSourceFileName(source,"");if path~=""then sources[#sources+1]=path end end
  end end
  tracks[#tracks+1]=string.format("%d. %s%s — MIDI items: %d, audio items: %d%s",i+1,n or"Track",reaper.IsTrackSelected(tr)and" [selected]"or"",midi_items,audio_items,#sources>0 and", audio: "..table.concat(sources,", ")or"")
 end
 local f=io.open(ROOT.."\\reaper_context.txt","w");if f then f:write(string.format("Tempo: %.2f BPM\nTime Signature: %d/%d\nSample Rate: %.0f Hz\nCursor: %.3f s\nTime Selection: %.3f - %.3f s\nTrack Count: %d\nTracks:\n%s\n",bpm,num,den,rate,cursor,a,b,reaper.CountTracks(0),table.concat(tracks,"\n")));f:close()end
end
local function json_quote(s)return '"'..tostring(s or""):gsub('\\','\\\\'):gsub('"','\\"'):gsub('\n','\\n')..'"'end
local function export_selected_midi()
 local notes,tracks={},{};local start_time,end_time=nil,nil
 for i=0,reaper.CountSelectedMediaItems(0)-1 do
  local item=reaper.GetSelectedMediaItem(0,i);local take=item and reaper.GetActiveTake(item)
  if take and reaper.TakeIsMIDI(take) then
   local _,take_guid=reaper.GetSetMediaItemTakeInfo_String(take,"GUID","",false);take_guid=take_guid:gsub("[{}]","")
   local track=reaper.GetMediaItemTrack(item);local _,name=reaper.GetTrackName(track,"");tracks[#tracks+1]=json_quote(name)
   local pos=reaper.GetMediaItemInfo_Value(item,"D_POSITION");local ending=pos+reaper.GetMediaItemInfo_Value(item,"D_LENGTH")
   start_time=not start_time and pos or math.min(start_time,pos);end_time=not end_time and ending or math.max(end_time,ending)
   local _,count=reaper.MIDI_CountEvts(take);local selected_count=0
   for n=0,count-1 do local ok,sel,muted,sp,ep,ch,pitch,vel=reaper.MIDI_GetNote(take,n);if ok and sel then selected_count=selected_count+1 end end
   for n=0,count-1 do
    local ok,sel,muted,sp,ep,ch,pitch,vel=reaper.MIDI_GetNote(take,n)
    if ok and (selected_count==0 or sel) then notes[#notes+1]=string.format('{"take_guid":%s,"pitch":%d,"velocity":%d,"start_ppq":%.3f,"end_ppq":%.3f,"channel":%d,"muted":%s}',json_quote(take_guid),pitch,vel,sp,ep,ch,muted and"true"or"false")end
   end
  end
 end
 if #notes==0 then return""end
 local source=ROOT.."\\selected-midi.json";local f=io.open(source,"w");if not f then return""end
 f:write('{"start_time":',string.format("%.3f",start_time or 0),',"end_time":',string.format("%.3f",end_time or 0),',"tracks":[',table.concat(tracks,","),'],"notes":[',table.concat(notes,","),']}');f:close();return source
end
local function start_worker()os.execute("powershell.exe -NoProfile -NonInteractive -Command \"Start-Process -WindowStyle Hidden -FilePath 'wsl.exe' -ArgumentList '-e bash /mnt/e/text2score/text2music/agent/launch_reaper_worker.sh'\"")end
local function stop_worker()local f=io.open(ROOT.."\\worker_queue\\shutdown","w");if f then f:write("panel closed\n");f:close()end end
local function cancel_generation(run)
 if run=="" then return end
 local f=io.open(run.."\\cancel","w");if f then f:write("cancelled from REAPER\n");f:close()end
end
local function clear_stale_error()
 local s=read(ROOT.."\\reaper-status.txt")
 if value(s,"STATE")=="error" then
  local f=io.open(ROOT.."\\reaper-status.txt","w")
  if f then f:write("STATE: ready\nPROGRESS: 0\nDETAIL: Starting local GPU music service\n");f:close()end
 end
end
local function submit_message(brief)
 local f=io.open(ROOT.."\\reaper_brief.txt","w");if not f then return end;f:write(brief);f:close();capture_context()
 local source=export_selected_midi()
 local args="-e bash /mnt/e/text2score/text2music/agent/launch_reaper_job.sh --brief-file /mnt/e/text2score/text2music/artifacts/agent_runs/reaper_brief.txt --context-file /mnt/e/text2score/text2music/artifacts/agent_runs/reaper_context.txt"
 if source~=""then args=args.." --source-midi /mnt/e/text2score/text2music/artifacts/agent_runs/selected-midi.json"end
 os.execute("powershell.exe -NoProfile -NonInteractive -Command \"Start-Process -WindowStyle Hidden -FilePath 'wsl.exe' -ArgumentList '"..args.."'\"")
end
local function open_prompt()
 if pending_prompt~="" then return end
 os.remove(PROMPT_RESULT);pending_prompt="chat"
 local command="Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','"..DIALOG.."','-Mode','Chat','-Output','"..PROMPT_RESULT.."')"
 os.execute("powershell.exe -NoProfile -NonInteractive -Command \""..command.."\"")
end
local function poll_prompt()
 if pending_prompt=="" or not exists(PROMPT_RESULT)then return end
 local brief=read(PROMPT_RESULT);os.remove(PROMPT_RESULT);pending_prompt=""
 if brief~=""then submit_message(brief)end
end
local function apply_midi_replacement()
 local path=ROOT.."\\midi-replacement.json";local data=read(path);if data==""then return end
 local groups={}
 for object in data:gmatch('{[^{}]-"take_guid"[^{}]-}')do
  local guid=object:match('"take_guid"%s*:%s*"([^"]+)"');local pitch=tonumber(object:match('"pitch"%s*:%s*(%d+)'))
  local velocity=tonumber(object:match('"velocity"%s*:%s*(%d+)'));local sp=tonumber(object:match('"start_ppq"%s*:%s*([%d%.%-]+)'));local ep=tonumber(object:match('"end_ppq"%s*:%s*([%d%.%-]+)'));local channel=tonumber(object:match('"channel"%s*:%s*(%d+)'))or 0
  local muted=object:match('"muted"%s*:%s*(%a+)')=="true"
  if guid and pitch and velocity and sp and ep then groups[guid]=groups[guid]or{};groups[guid][#groups[guid]+1]={pitch=pitch,velocity=velocity,sp=sp,ep=ep,channel=channel,muted=muted}end
 end
 reaper.Undo_BeginBlock()
 for ti=0,reaper.CountTracks(0)-1 do local track=reaper.GetTrack(0,ti)
  for ii=0,reaper.CountTrackMediaItems(track)-1 do local item=reaper.GetTrackMediaItem(track,ii)
   for tk=0,reaper.CountTakes(item)-1 do local take=reaper.GetTake(item,tk);if take and reaper.TakeIsMIDI(take)then
    local _,guid=reaper.GetSetMediaItemTakeInfo_String(take,"GUID","",false);guid=guid:gsub("[{}]","");local notes=groups[guid]
    if notes then
     local _,count=reaper.MIDI_CountEvts(take);local selected=0
     for n=0,count-1 do local ok,sel=reaper.MIDI_GetNote(take,n);if ok and sel then selected=selected+1 end end
     for n=count-1,0,-1 do local ok,sel=reaper.MIDI_GetNote(take,n);if ok and(selected==0 or sel)then reaper.MIDI_DeleteNote(take,n)end end
     local max_ep=0;for _,note in ipairs(notes)do reaper.MIDI_InsertNote(take,true,note.muted,note.sp,note.ep,note.channel,note.pitch,note.velocity,true);max_ep=math.max(max_ep,note.ep)end
     reaper.MIDI_Sort(take);local ending=reaper.MIDI_GetProjTimeFromPPQPos(take,max_ep);local start=reaper.GetMediaItemInfo_Value(item,"D_POSITION");if ending>start then reaper.SetMediaItemInfo_Value(item,"D_LENGTH",ending-start)end
    end
   end end
  end
 end
 reaper.Undo_EndBlock("Triceratops replace selected MIDI",-1);os.remove(path);reaper.UpdateArrange()
end
local function poll_command()
 local path=ROOT.."\\reaper-command.txt";local taken=path..".taken"
 -- Atomic claim: the one-shot import action may race us for the same file.
 if os.rename(path,taken)~=true then return end
 local payload=read(taken);os.remove(taken);local command=value(payload,"COMMAND")
 if command=="undo"then reaper.Undo_DoUndo2(0)
 elseif command=="accept"then
  local midi=value(read(ROOT.."\\reaper-status.txt"),"MIDI");local f=io.open(ROOT.."\\accepted-version.txt","w");if f then f:write(midi.."\n");f:close()end
 elseif command=="replace_selection"then apply_midi_replacement()
 elseif command=="import_midi_file"or command=="import_audio_stems"then
  local files=value(payload,"FILES");reaper.Undo_BeginBlock()
  for file in files:gmatch("[^|]+")do
   local index=reaper.CountTracks(0);reaper.InsertTrackAtIndex(index,true);local track=reaper.GetTrack(0,index)
   local name=file:match("([^/\\]+)%.%w+$")or"Agent Import";reaper.GetSetMediaTrackInfo_String(track,"P_NAME",name,true)
   reaper.SetOnlyTrackSelected(track);reaper.InsertMedia(file,0)
  end
  reaper.TrackList_AdjustWindows(false);reaper.Undo_EndBlock("Triceratops import analyzed media",-1)
 end
end
local function button(label,x,y,w,enabled,kind,height,label_size)
 local h=height or 58;local fs=label_size or 18
 local hit=enabled and gfx.mouse_x>=x and gfx.mouse_x<=x+w and gfx.mouse_y>=y and gfx.mouse_y<=y+h
 local down=hit and(gfx.mouse_cap&1)==1
 local target=hit and 1 or 0;local motion=button_motion[label]or 0;motion=motion+(target-motion)*.24;button_motion[label]=motion
 local r,g,b=kind=="primary"and .31 or .78,kind=="primary"and .75 or .85,kind=="primary"and .69 or .80
 if not enabled then r,g,b=.82,.83,.80 end
 r=math.min(1,r+motion*.08);g=math.min(1,g+motion*.07);b=math.min(1,b+motion*.04)
 local inset=down and 3 or-motion*2;local yy=y+(down and 3 or-motion*1.5);local ww=w-inset*2;local hh=h-(down and 3 or 0)
 if motion>.03 and not down then c(.03,.025,.018,.14*motion);gfx.roundrect(x+2,y+4,w,h,math.min(16,h*.4),1)end
 card(x+inset,yy,ww,hh,r,g,b,math.min(16,h*.4));text(label,x+16+(down and 2 or 0),y+math.max(7,(h-fs)/2)+(down and 3 or 0),fs,enabled and .05 or .38,enabled and .16 or .4,enabled and .20 or .42,true)
 return hit
end
local function loop()
 poll_prompt();poll_command()
 local status=read(ROOT.."\\reaper-status.txt");local state=value(status,"STATE");local pct=tonumber(value(status,"PROGRESS"))or 0;local detail=value(status,"DETAIL");local plan=value(status,"PLAN");local midi=value(status,"MIDI");local run=value(status,"RUN");local source_midi=value(status,"SOURCE_MIDI")
 local worker=value(read(ROOT.."\\worker_queue\\worker-state.txt"),"STATE")
 if (state=="" or state=="ready") and worker=="loading" then
  local elapsed=math.floor(reaper.time_precise()-panel_opened)
  state="loading_model";pct=math.min(55,4+elapsed)
  detail="Loading the Triceratops music model — "..elapsed.."s elapsed."
 end
 if state=="" and worker=="ready" then state="ready";detail="Local GPU model is warm and ready." end
 if state=="completed"and midi~=""and midi~=imported and midi~=rejected then
  reaper.Undo_BeginBlock()
  if source_midi~="" then
   local index=reaper.CountTracks(0);reaper.InsertTrackAtIndex(index,true);local candidate=reaper.GetTrack(0,index);reaper.GetSetMediaTrackInfo_String(candidate,"P_NAME","Triceratops Revision Candidate",true);reaper.SetOnlyTrackSelected(candidate)
  else prepare_tracks(plan,run)end
  reaper.InsertMedia(midi,0);imported=midi;reaper.TrackList_AdjustWindows(false);reaper.Undo_EndBlock("Triceratops import MIDI version",-1)
 end
 local busy=active(state);local clicked=(gfx.mouse_cap&1)==1 and not mouse_down
 -- Solid milk-yellow surface: no image, texture, pattern, or gradient.
 c(.96,.90,.70);gfx.rect(0,0,gfx.w,gfx.h,1)
 card(24,22,142,gfx.h-44,.87,.72,.35,22)
 -- Ultra-minimal triceratops mark: frill, twin horns and central face axis.
 c(.03,.025,.018);gfx.line(43,91,57,58);gfx.line(57,58,78,45);gfx.line(78,45,99,58);gfx.line(99,58,113,91)
 gfx.line(57,58,45,34);gfx.line(99,58,111,34);gfx.line(63,74,93,74);gfx.line(78,74,78,98)
 text("TRICERA",43,132,16,.96,.88,.61,true);text("TOPS",43,157,21,.96,.88,.61,true);text("MUSIC AGENT",43,188,11,.42,.91,.84,true)
 c(.22,.78,.72);gfx.rect(47,216,92,1,1);text("CREATE",47,242,13,.96,.90,.67,true);text("MIDI SHAPE",47,280,13,.72,.88,.82,true);text("VERSIONS",47,318,13,.72,.88,.82,true)
 text("v7.0",47,gfx.h-57,12,.72,.84,.78);text("LOCAL GPU",47,gfx.h-35,11,.55,.91,.85,true)
 card(190,22,gfx.w-214,198,.99,.94,.78,24)
 text("A score, shaped by intent.",220,57,34,.94,.89,.75,true)
 text("Triceratops listens to your idea and your REAPER session.",222,104,17,.72,.84,.81)
 text("tempo  /  meter  /  track context  /  MIDI history",222,137,14,.37,.78,.74,true)
 local sr,sg,sb=.86,.80,.56;if state=="completed"then sr,sg,sb=.64,.84,.64 elseif state=="error"then sr,sg,sb=.94,.62,.52 elseif state=="cancelled"then sr,sg,sb=.91,.76,.43 elseif busy then sr,sg,sb=.66,.82,.72 end
 card(222,165,190,31,sr,sg,sb,15);text(state==""and"READY TO CREATE"or state:upper(),241,175,12,.94,.89,.75,true)
 -- One conversational entry point; the backend chooses tools and intent.
 card(190,244,gfx.w-214,138,.99,.94,.79,20);text("Message Triceratops",216,267,22,.94,.89,.75,true)
 local latest=read(ROOT.."\\conversation-latest.txt")
 text(latest~=""and clipped(latest,86)or"Ask for new music, modify selected MIDI, check progress, cancel, keep, or undo.",216,300,15,.70,.82,.79)
 text("NEW MUSIC  ·  EDIT MIDI  ·  ANALYZE  ·  STEMS",216,336,13,.70,.82,.79,true)
 local chat=button("Open message composer",gfx.w-350,306,312,pending_prompt=="","primary")
 if clicked and chat then open_prompt()end;mouse_down=(gfx.mouse_cap&1)==1
 -- Status is deliberately readable: dark text only, generous type and one explicit progress bar.
 card(190,388,gfx.w-214,122,.94,.84,.56,20)
 local headline=state=="completed"and"Your MIDI is ready."or(state=="cancelled"and"Generation cancelled."or(state=="error"and"The agent needs attention."or(state=="analyzing_audio"and"Listening to project audio"or(state=="loading_model"and"Warming the local model"or(state=="sampling"and"Sampling notation"or(busy and"Planning your arrangement"or"Ready when inspiration strikes."))))))
 text(headline,216,412,25,.95,.90,.76,true)
 text(detail~=""and clipped(detail,100)or"Describe a musical direction and the agent will plan, compose and import MIDI.",216,448,16,.73,.84,.81)
 local indeterminate=state=="loading_model"
 if not indeterminate then text(string.format("%d%%",pct),gfx.w-285,414,28,.32,.88,.81,true)end
 card(216,480,gfx.w-310,10,.76,.65,.37,5)
 if indeterminate then local span=math.min(150,(gfx.w-310)*.18);local travel=(gfx.w-310)-span;local x=216+(math.floor(reaper.time_precise()*130)%math.max(1,travel));card(x,480,span,10,.08,.07,.05,5) elseif pct>0 then card(216,480,(gfx.w-310)*math.min(pct,100)/100,10,.08,.07,.05,5)end
 -- Arrangement and history
 local lw=math.floor((gfx.w-248)*.62);card(190,536,lw,gfx.h-560,.99,.94,.79,18);local rx=206+lw
 text("ARRANGEMENT",216,559,13,.36,.82,.77,true)
 local plan_text=read(plan~=""and plan or ROOT.."\\current-plan.txt");if plan_text==""then plan_text="Your arrangement will appear here. Tempo, meter and track context are taken from the current REAPER project."end
 local lines={};for line in plan_text:gmatch("[^\n]+")do lines[#lines+1]=line end
 local content_y=590;local content_bottom=gfx.h-40;local visible=math.max(1,math.floor((content_bottom-content_y)/23));local max_scroll=math.max(0,#lines-visible)
 arrangement_scroll=math.max(0,math.min(max_scroll,arrangement_scroll))
 local over_arrangement=gfx.mouse_x>=190 and gfx.mouse_x<=190+lw and gfx.mouse_y>=536 and gfx.mouse_y<=gfx.h-24
 if over_arrangement and gfx.mouse_wheel~=0 then arrangement_scroll=math.max(0,math.min(max_scroll,arrangement_scroll-math.floor(gfx.mouse_wheel/120)));gfx.mouse_wheel=0 end
 for i=1,visible do local line=lines[i+arrangement_scroll];if not line then break end;text(clipped(line,68),216,content_y+(i-1)*23,15,.82,.87,.80,true)end
 local track_x,track_y,track_h=190+lw-18,586,math.max(30,gfx.h-626)
 card(track_x,track_y,7,track_h,.84,.75,.49,4)
 if max_scroll>0 then
  local thumb_h=math.max(34,track_h*visible/#lines);local thumb_y=track_y+(track_h-thumb_h)*(arrangement_scroll/max_scroll)
  local over_thumb=gfx.mouse_x>=track_x-5 and gfx.mouse_x<=track_x+13 and gfx.mouse_y>=thumb_y and gfx.mouse_y<=thumb_y+thumb_h
  if (gfx.mouse_cap&1)==1 and over_thumb and not arrangement_dragging then arrangement_dragging=true;arrangement_drag_offset=gfx.mouse_y-thumb_y end
  if (gfx.mouse_cap&1)==0 then arrangement_dragging=false end
  if arrangement_dragging then
   local ratio=math.max(0,math.min(1,(gfx.mouse_y-arrangement_drag_offset-track_y)/math.max(1,track_h-thumb_h)))
   arrangement_scroll=math.floor(ratio*max_scroll+.5);thumb_y=track_y+(track_h-thumb_h)*(arrangement_scroll/max_scroll)
  elseif clicked and gfx.mouse_x>=track_x-5 and gfx.mouse_x<=track_x+13 and gfx.mouse_y>=track_y and gfx.mouse_y<=track_y+track_h then
   local ratio=math.max(0,math.min(1,(gfx.mouse_y-track_y-thumb_h/2)/math.max(1,track_h-thumb_h)))
   arrangement_scroll=math.floor(ratio*max_scroll+.5);thumb_y=track_y+(track_h-thumb_h)*(arrangement_scroll/max_scroll)
  end
  card(track_x,thumb_y,7,thumb_h,.08,.07,.05,4)
 end
 card(rx,536,gfx.w-rx-24,gfx.h-560,.99,.94,.79,18);text("AGENT TRACE",rx+24,559,13,.36,.82,.77,true);local trace=run~=""and read(run.."\\agent-trace.jsonl")or"";local hist=read(ROOT.."\\reaper-history.jsonl");text(trace~=""and clipped(trace:sub(-800),280)or(hist==""and"No completed MIDI versions yet."or clipped(hist:sub(-800),280)),rx+24,592,15,.82,.87,.80)
 text("Finished MIDI stays in your project history when this panel closes.",190,gfx.h-25,13,.54,.73,.70)
 if gfx.getchar()>=0 then reaper.defer(loop)else stop_worker()end
end
clear_stale_error();start_worker();gfx.init("Triceratops",1240,800);reaper.defer(loop)
