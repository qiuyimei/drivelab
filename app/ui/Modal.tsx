'use client';
import {useEffect,useRef,type ReactNode} from 'react';

export function Modal({label,onClose,children}:{label:string;onClose:()=>void;children:ReactNode}){
 const ref=useRef<HTMLDialogElement>(null);
 useEffect(()=>{
  const dialog=ref.current;
  const previous=document.activeElement instanceof HTMLElement?document.activeElement:null;
  if(dialog&&!dialog.open)dialog.showModal();
  return()=>{dialog?.close();if(previous?.isConnected)previous.focus();};
 },[]);
 return <dialog ref={ref} className="modal-backdrop" aria-label={label} onCancel={e=>{e.preventDefault();onClose();}} onClick={e=>{if(e.target===e.currentTarget)onClose();}}><section className="modal">{children}</section></dialog>;
}
